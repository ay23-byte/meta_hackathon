"""Plan acquisition and strict validation for the analysis agent.

Muse Spark proposes a *plan* (tool names + parameters), never code. A plan is
executed only after ``validate_plan`` accepts it. When the provider is
unavailable, ``deterministic_plan`` produces an equivalent schema-aware plan
that goes through the same validated dispatch.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

import ask_muse
import provider_config
from agent_tools import MAX_DEGREE, MAX_FALLBACK_MODELS, MAX_STEPS, registry_manifest
from fitting_core import MODEL_SPECS

MAX_PLAN_CHARS = 32_000
MAX_RAW_PLAN_CHARS = 64_000
MAX_TEXT_FIELD = 300
MAX_PLAN_TOKENS = 2048
FORBIDDEN_PLAN_TOKENS = ("```", "import ", "__", "os.system", "eval(", "exec(", "subprocess", "lambda ", "open(")

PLAN_KEYS = {"dataset_understanding", "steps", "on_poor_fit", "stop_condition"}
STEP_KEYS = {"tool", "params", "rationale"}


class PlannerUnavailable(RuntimeError):
    """Raised when a live plan cannot be obtained; callers fall back safely."""


@dataclass
class PlanValidation:
    accepted: bool
    plan: dict | None = None
    reasons: list[str] = field(default_factory=list)
    rejected_steps: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"accepted": self.accepted, "plan": self.plan,
                "reasons": self.reasons, "rejected_steps": self.rejected_steps}


def build_plan_prompt(quality: dict, manifest: list[dict] | None = None,
                      research_question: str | None = None) -> str:
    """Prompt contains schema facts, the user's question and the tool allowlist."""
    manifest = manifest if manifest is not None else registry_manifest()
    context = json.dumps({
        "research_question": str(research_question or "")[:MAX_TEXT_FIELD],
        "data_quality": quality, "available_tools": manifest,
    }, ensure_ascii=False, allow_nan=False, default=str)
    if len(context) > MAX_PLAN_CHARS:
        raise ValueError("The planning context exceeds its size limit.")
    return f"""
You are an analysis planner for a scientific dataset. You may ONLY choose tools
from the supplied allowlist and ONLY supply parameters declared for those tools.
You cannot run code, access files, or invent measurements.

Return ONE valid JSON object, no prose and no markdown fences, with exactly
these top-level keys:
{{
  "dataset_understanding": "at most 40 words",
  "steps": [
    {{"tool": "allowed tool name", "params": {{}}, "rationale": "short reason"}}
  ],
  "on_poor_fit": {{"strategy": "try_alternatives or halt_and_explain",
                   "fallback_models": ["model name", "..."]}},
  "stop_condition": "short statement"
}}

Rules:
- At most {MAX_STEPS} steps. Include exactly one `fit_curve` step and one
  `diagnose_fit` step whose `fit_ref` is "fit_1" (the first fit's reference).
- `fit_curve.model` must be one of {list(MODEL_SPECS)}; `degree` (if used) is
  at most {MAX_DEGREE}; `weights` is null unless an uncertainty column exists.
- `method` must be pearson or spearman. Column names must appear in the schema.
- `fallback_models` has at most {MAX_FALLBACK_MODELS} entries drawn from the
  model list above. Use "halt_and_explain" when no alternative is justified.
- Never state a numerical result: all numbers come from executing the tools.
- Tailor the steps to the supplied research question; ask for clarification
  in `stop_condition` if the question cannot be answered with these tools.
- Do not include code, imports, file paths, shell commands, or private names.

Dataset schema and tool allowlist:
{context}
""".strip()


def _extract_json(text: str) -> dict:
    candidate = text.strip()
    if len(candidate) > MAX_RAW_PLAN_CHARS:
        raise ValueError("plan response is oversized")
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        lines = lines[1:] if lines and lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("plan is not a JSON object")
    return parsed


def request_agent_plan(quality: dict, manifest: list[dict] | None = None,
                       research_question: str | None = None) -> dict:
    """Ask Muse Spark for a plan. Raises PlannerUnavailable on any failure."""
    api_key = provider_config.get_api_key()
    if not api_key:
        raise PlannerUnavailable("BASETEN_API_KEY is not configured")
    prompt = build_plan_prompt(quality, manifest, research_question)
    if len(prompt) > ask_muse.MAX_PROMPT_CHARS:
        raise PlannerUnavailable("planning prompt exceeds the size limit")
    try:
        # Use the same provider conventions as the interpretation adapter.
        original_tokens = ask_muse.MAX_COMPLETION_TOKENS
        ask_muse.MAX_COMPLETION_TOKENS = MAX_PLAN_TOKENS
        try:
            client = ask_muse.OpenAI(
                api_key=api_key, base_url=ask_muse.BASE_URL,
                timeout=ask_muse.REQUEST_TIMEOUT_SECONDS, max_retries=0,
            )
            response = ask_muse._completion_request(
                client, prompt, json_mode=True, modern_tokens=True
            )
        finally:
            ask_muse.MAX_COMPLETION_TOKENS = original_tokens
    except Exception as exc:
        raise PlannerUnavailable(f"provider request failed ({type(exc).__name__})") from None

    choices = getattr(response, "choices", None)
    if not choices:
        raise PlannerUnavailable("provider returned no choices")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if not isinstance(content, str) or not content.strip():
        raise PlannerUnavailable("provider returned no visible plan content")
    try:
        return _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise PlannerUnavailable(f"provider returned an invalid plan: {exc}") from None


def validate_plan(raw, allowed_tools: list[str] | None = None,
                  allowed_models: list[str] | None = None) -> PlanValidation:
    """Strictly validate a proposed plan before ANY tool is executed."""
    allowed_tools = list(allowed_tools or [spec["tool"] for spec in registry_manifest()])
    allowed_models = list(allowed_models or MODEL_SPECS)
    reasons: list[str] = []
    rejected: list[dict] = []
    if not isinstance(raw, dict):
        return PlanValidation(False, None, ["plan must be a JSON object"])
    extra_keys = set(raw) - PLAN_KEYS
    if extra_keys:
        reasons.append(f"unexpected top-level keys: {sorted(extra_keys)}")
    for key in PLAN_KEYS:
        if key not in raw:
            reasons.append(f"missing top-level key: {key}")

    blob = json.dumps(raw, ensure_ascii=False, default=str)
    for token in FORBIDDEN_PLAN_TOKENS:
        if token in blob:
            reasons.append(f"plan contains a forbidden token: {token!r}")
    for key in ("dataset_understanding", "stop_condition"):
        value = raw.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > MAX_TEXT_FIELD):
            reasons.append(f"{key} must be a short string")

    steps = raw.get("steps")
    if not isinstance(steps, list) or not (1 <= len(steps) <= MAX_STEPS):
        reasons.append(f"steps must be a list of 1..{MAX_STEPS} items")
        steps = []
    seen: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            reasons.append(f"step {index} is not an object")
            rejected.append({"index": index, "reason": "not an object"})
            continue
        step_extra = set(step) - STEP_KEYS
        if step_extra:
            reasons.append(f"step {index} has unexpected keys: {sorted(step_extra)}")
        tool = step.get("tool")
        params = step.get("params")
        rationale = step.get("rationale")
        if tool not in allowed_tools:
            reasons.append(f"step {index} uses an unknown tool: {tool!r}")
            rejected.append({"index": index, "tool": tool, "reason": "unknown tool"})
            continue
        if not isinstance(params, dict):
            reasons.append(f"step {index} params must be an object")
            rejected.append({"index": index, "tool": tool, "reason": "invalid params"})
            continue
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > MAX_TEXT_FIELD:
            reasons.append(f"step {index} needs a short rationale")
        signature = f"{tool}:{json.dumps(params, sort_keys=True, default=str)}"
        if signature in seen:
            reasons.append(f"step {index} duplicates an earlier step")
            rejected.append({"index": index, "tool": tool, "reason": "duplicate step"})
        seen.add(signature)
        if tool == "fit_curve":
            model = params.get("model")
            if model not in allowed_models:
                reasons.append(f"step {index} requests an unknown model: {model!r}")
            degree = params.get("degree")
            if degree is not None and (not isinstance(degree, int)
                                      or isinstance(degree, bool)
                                      or not 1 <= degree <= MAX_DEGREE):
                reasons.append(f"step {index} degree is out of range")
            for token in ("x", "y"):
                if not isinstance(params.get(token), str):
                    reasons.append(f"step {index} needs a string '{token}' column")
        if tool == "correlation_analysis" and params.get("method") not in ("pearson", "spearman"):
            reasons.append(f"step {index} has an invalid correlation method")

    on_poor = raw.get("on_poor_fit")
    strategy = None
    fallback: list[str] = []
    if not isinstance(on_poor, dict):
        reasons.append("on_poor_fit must be an object")
    else:
        strategy = on_poor.get("strategy")
        if strategy not in ("try_alternatives", "halt_and_explain"):
            reasons.append("on_poor_fit.strategy is invalid")
        fallback = on_poor.get("fallback_models")
        if not isinstance(fallback, list) or len(fallback) > MAX_FALLBACK_MODELS:
            reasons.append(f"fallback_models must be a list of at most {MAX_FALLBACK_MODELS}")
            fallback = []
        else:
            for model in fallback:
                if model not in allowed_models:
                    reasons.append(f"unknown fallback model: {model!r}")
            if strategy == "halt_and_explain" and fallback:
                reasons.append("halt_and_explain must not supply fallback models")

    if reasons:
        return PlanValidation(False, None, reasons, rejected)
    plan = {
        "dataset_understanding": raw["dataset_understanding"],
        "steps": [{"tool": s["tool"], "params": s["params"], "rationale": s["rationale"]}
                  for s in steps],
        "on_poor_fit": {"strategy": strategy, "fallback_models": list(fallback)},
        "stop_condition": raw["stop_condition"],
    }
    return PlanValidation(True, plan, [], [])


def deterministic_plan(quality: dict) -> dict:
    """Schema-aware offline plan used when no provider is available."""
    x = quality.get("suggested_x")
    y = quality.get("suggested_y")
    columns = [c for c in (quality.get("numeric_columns") or [])[:6]]
    steps = [
        {"tool": "profile_columns", "params": {}, "rationale": "Confirm inferred column types."},
        {"tool": "describe_statistics", "params": {"columns": columns},
         "rationale": "Establish deterministic location and spread."},
        {"tool": "correlation_analysis",
         "params": {"x": x, "y": y, "method": "pearson"},
         "rationale": "Measure linear association before fitting."},
        {"tool": "render_plot", "params": {"plot_type": "scatter", "x": x, "y": y},
         "rationale": "Inspect the observed pattern."},
        {"tool": "fit_curve", "params": {"x": x, "y": y, "model": "linear"},
         "rationale": "Start with the simplest justified model."},
        {"tool": "diagnose_fit", "params": {"fit_ref": "fit_1"},
         "rationale": "Check fit quality before drawing a conclusion."},
        {"tool": "compare_models",
         "params": {"x": x, "y": y, "models": ["linear", "polynomial"]},
         "rationale": "Compare computed fit metrics without assuming the first model is best."},
        {"tool": "evidence_summary", "params": {},
         "rationale": "Record result IDs for evidence-linked claims in the final report."},
    ]
    return {
        "dataset_understanding": "Automatically generated offline plan: describe, plot, fit, diagnose.",
        "steps": steps,
        "on_poor_fit": {"strategy": "try_alternatives",
                        "fallback_models": ["polynomial", "exponential"]},
        "stop_condition": "Stop when diagnostics pass or the attempt budget is exhausted.",
    }


def plan_hash(plan: dict | None) -> str:
    if not plan:
        return ""
    return "sha256:" + hashlib.sha256(
        json.dumps(plan, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Grounded final interpretation
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


def evidence_numbers(results: list[dict]) -> list[float]:
    """Collect every numeric value actually produced by executed tools."""
    blob = json.dumps(results, ensure_ascii=False, default=str)
    return [float(match) for match in _NUMBER.findall(blob)]


def grounding_check(text: str, results: list[dict]) -> dict:
    """Reject AI prose containing numbers absent from the tool outputs."""
    observed = evidence_numbers(results)
    claimed = [float(match) for match in _NUMBER.findall(text or "")]
    unsupported = []
    for value in claimed:
        if not any(abs(value - ref) <= 1e-6 * max(1.0, abs(ref)) for ref in observed):
            unsupported.append(value)
    return {"pass": not unsupported, "unsupported_values": unsupported[:10],
            "checked_values": len(claimed)}


def generate_grounded_interpretation(audit_digest: dict) -> dict | None:
    """Optional Muse Spark report built ONLY from executed tool outputs."""
    if not provider_config.get_api_key():
        return None
    context = {
        "note": "Use only these executed tool outputs. Never invent numbers.",
        "dataset": audit_digest.get("dataset"),
        "research_question": audit_digest.get("research_question"),
        "quality": audit_digest.get("quality_summary"),
        "tool_results": audit_digest.get("tool_results"),
        "decisions": audit_digest.get("decisions"),
        "final_state": audit_digest.get("final", {}).get("state"),
    }
    try:
        wrapper = ask_muse.generate_interpretation(context)
    except (ValueError, RuntimeError):
        return None
    prose = " ".join(
        section.get("content", "") for section in wrapper["structured"]["sections"]
    )
    check = grounding_check(prose, context["tool_results"])
    if not check["pass"]:
        return {"rejected": True, "grounding_check": check}
    return {"model": wrapper.get("model"), "structured": wrapper["structured"],
            "grounding_check": check}


def deterministic_conclusion(audit_digest: dict) -> str:
    """Final text assembled exclusively from executed tool outputs."""
    final = audit_digest.get("final") or {}
    state = final.get("state")
    results = audit_digest.get("tool_results") or []
    fits = [r for r in results if r.get("tool") == "fit_curve" and r.get("ok")]
    if state != "DONE" or not fits:
        reasons = final.get("reasons") or ["No model met the diagnostic thresholds."]
        return ("Insufficient evidence for a supported quantitative conclusion. "
                + " ".join(str(reason) for reason in reasons[:3]))
    last = fits[-1]
    payload = last.get("result", {}) or {}
    metrics = payload.get("metrics") or {}
    r2 = metrics.get("r2")
    rmse = metrics.get("rmse")
    n = payload.get("n_observations")
    model = payload.get("model")
    equation = payload.get("equation")
    parts = [
        f"Executed tools produced a successful {model} fit on {n} complete observations.",
    ]
    if equation:
        parts.append(f"Equation: {equation}.")
    if r2 is not None:
        parts.append(f"R2 = {r2:.6g}; RMSE = {rmse:.6g}." if rmse is not None else f"R2 = {r2:.6g}.")
    if final.get("retries"):
        parts.append(f"{len(final['retries'])} bounded retry was required." )
    parts.append("These are computed results, not measurements beyond the fitted range.")
    return " ".join(parts)
