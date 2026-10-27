"""Bounded analysis orchestrator.

Flow: inspect -> (Muse Spark or offline) plan -> strict validation -> execute
allowlisted tools -> observe -> deterministic diagnostics -> bounded retry ->
grounded interpretation -> audit trail. All numbers come from tool outputs.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pandas as pd

import agent_planner as planner
from agent_audit import AgentRun
from agent_diagnostics import PASS, choose_alternative, classify_quality
from agent_tools import (
    MAX_FIT_ATTEMPTS,
    MAX_RETRIES,
    MAX_STEPS,
    MAX_WALL_S,
    ToolContext,
    execute_tool,
)

DONE = "DONE"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
FAILED = "FAILED"


@dataclass
class OrchestratorConfig:
    use_ai: bool | None = None
    user_confirmed: bool = False
    max_steps: int = MAX_STEPS
    max_retries: int = MAX_RETRIES
    max_fit_attempts: int = MAX_FIT_ATTEMPTS
    max_wall_s: float = MAX_WALL_S
    plan_provider: object = None       # callable(quality) -> raw plan (test seam)
    interpretation_provider: object = None  # callable(audit_digest) -> report|None


class AnalysisOrchestrator:
    """Executes one analysis run. No method evaluates model-generated code."""

    def __init__(self, config: OrchestratorConfig | None = None, **kwargs):
        self.config = config or OrchestratorConfig(**kwargs)
        if self.config.use_ai is None:
            self.config.use_ai = bool(os.getenv("BASETEN_API_KEY", "").strip())

    # ------------------------------------------------------------------
    def run(self, load, frame: pd.DataFrame | None = None) -> AgentRun:
        source = frame if frame is not None else load.frame
        load_info = {
            "name": getattr(load, "source_name", "dataset.csv"),
            "sha256": getattr(load, "sha256", ""),
            "rows": len(source),
            "columns": [str(c) for c in source.columns],
            "delimiter": getattr(load, "delimiter", ","),
            "encoding": getattr(load, "encoding", "utf-8"),
            "duplicate_headers": list(getattr(load, "duplicate_headers", []) or []),
            "warnings": list(getattr(load, "warnings", []) or []),
        }
        limits = {
            "max_steps": self.config.max_steps,
            "max_retries": self.config.max_retries,
            "max_fit_attempts": self.config.max_fit_attempts,
            "max_wall_s": self.config.max_wall_s,
        }
        run = AgentRun(dataset=load_info, limits=limits)
        ctx = ToolContext(
            frame=source, load_info=load_info,
            deadline=time.monotonic() + self.config.max_wall_s,
            user_confirmed=self.config.user_confirmed,
        )

        # 1. Inspect -----------------------------------------------------
        inspected = execute_tool("inspect_dataset", {}, ctx)
        run.log_tool(inspected, phase="inspect", decision="deterministic data-quality summary")
        if not inspected.ok:
            run.quality_summary = {"error": inspected.error}
            run.finalize(state=FAILED, conclusion="Inspection failed; no analysis was run.",
                         reasons=[inspected.error or "inspection failed"])
            return run
        quality = inspected.result
        run.quality_summary = quality

        # 2. Deterministic quality gate ----------------------------------
        gate = classify_quality(quality)
        run.log(phase="quality_gate", actor="deterministic", status="ok",
                result_digest=gate, decision=gate["decision"])
        if gate["decision"] != "CONTINUE":
            state = (NEEDS_CLARIFICATION if gate["decision"] == "NEEDS_CLARIFICATION"
                     else INSUFFICIENT_EVIDENCE)
            run.finalize(state=state,
                         conclusion=("The agent halted before fitting. " + " ".join(gate["reasons"])),
                         reasons=gate["reasons"],
                         evidence_refs=[1])
            return run
        for recovery in gate["recovery"]:
            run.log(phase="recovery", actor="deterministic", status="ok",
                    result_digest={"action": recovery},
                    decision="recovery without deleting or imputing observations")

        # 3. Plan + validate ---------------------------------------------
        plan = self._acquire_plan(run, quality)
        strategy = plan["on_poor_fit"]["strategy"]
        fallback_models = list(plan["on_poor_fit"]["fallback_models"])

        # 4/5. Execute approved tools and observe ------------------------
        x_col, y_col = quality.get("suggested_x"), quality.get("suggested_y")
        fit_refs: list[str] = []
        tried_models: list[str] = []
        last_diagnosis: dict = {}
        diagnosis_seq: int | None = None
        fit_seq: dict[str, int] = {}
        terminal_declaration = None

        for step in plan["steps"][: self.config.max_steps]:
            if time.monotonic() > ctx.deadline:
                run.log(phase="bounds", actor="deterministic", status="error",
                        decision="global deadline exceeded")
                break
            tool, params = step["tool"], dict(step["params"])
            if tool == "inspect_dataset":
                run.log(phase="execute", actor="ai", tool=tool, params=params,
                        status="skipped", decision="inspection already completed")
                continue
            if tool == "diagnose_fit" and params.get("fit_ref") == "fit_1" and fit_refs:
                params["fit_ref"] = fit_refs[0]
            result = execute_tool(tool, params, ctx)
            decision = ("AI-selected tool" if run.plan_source.startswith("muse")
                        else "validated plan step")
            seq = run.log_tool(result, phase="execute", decision=decision)
            if not result.ok:
                continue
            if tool == "fit_curve":
                ref = result.result.get("fit_ref")
                if ref:
                    fit_refs.append(ref)
                    fit_seq[ref] = seq
                    tried_models.append(params.get("model"))
            elif tool == "diagnose_fit":
                last_diagnosis = result.result.get("diagnosis") or {}
                diagnosis_seq = seq
            elif tool == "declare_insufficient":
                terminal_declaration = params.get("reason")

        # Guarantee a fit and a diagnosis even for a minimal valid plan.
        if not fit_refs:
            default_fit = execute_tool("fit_curve", {"x": x_col, "y": y_col,
                                                     "model": "linear"}, ctx)
            seq = run.log_tool(default_fit, phase="execute",
                               decision="default fit added: plan contained no fit step")
            if default_fit.ok:
                ref = default_fit.result.get("fit_ref")
                fit_refs.append(ref)
                fit_seq[ref] = seq
                tried_models.append("linear")
        if fit_refs and not last_diagnosis:
            diag = execute_tool("diagnose_fit", {"fit_ref": fit_refs[-1]}, ctx)
            diagnosis_seq = run.log_tool(diag, phase="execute",
                                         decision="default diagnosis added")
            if diag.ok:
                last_diagnosis = diag.result.get("diagnosis") or {}

        # 6/7. Bounded retry with validated alternatives -----------------
        if terminal_declaration:
            last_diagnosis = {"verdict": "INSUFFICIENT", "reasons": [terminal_declaration]}

        while (
            last_diagnosis.get("verdict") in ("POOR_FIT", "FAILED")
            and len(fit_refs) < self.config.max_fit_attempts
            and len(run.retries) < self.config.max_retries
            and strategy == "try_alternatives"
            and time.monotonic() <= ctx.deadline
        ):
            alternative = choose_alternative(tried_models, fallback_models,
                                             self.config.max_fit_attempts)
            if alternative is None:
                run.log(phase="retry", actor="deterministic", status="stopped",
                        decision="no untried validated alternative remains")
                break
            retry_params = {"x": x_col, "y": y_col, "model": alternative}
            if alternative == "polynomial":
                retry_params["degree"] = 2
            previous = last_diagnosis.get("verdict")
            fit_result = execute_tool("fit_curve", retry_params, ctx)
            fit_event_seq = run.log_tool(
                fit_result, phase="retry",
                decision=f"retry after {previous}: linear -> {alternative}",
            )
            if not fit_result.ok:
                run.retries.append({"attempt": len(run.retries) + 1,
                                    "from": tried_models[-1], "to": alternative,
                                    "reason": fit_result.error, "status": "failed"})
                tried_models.append(alternative)
                continue
            new_ref = fit_result.result.get("fit_ref")
            fit_refs.append(new_ref)
            fit_seq[new_ref] = fit_event_seq
            diag = execute_tool("diagnose_fit", {"fit_ref": new_ref}, ctx)
            diagnosis_seq = run.log_tool(diag, phase="retry",
                                         decision="re-diagnose alternative fit")
            if diag.ok:
                last_diagnosis = diag.result.get("diagnosis") or {}
            run.retries.append({
                "attempt": len(run.retries) + 1,
                "from": tried_models[-1], "to": alternative,
                "reason": "; ".join([str(r) for r in (last_diagnosis.get("reasons") or [])] or [str(previous)]),
                "previous_verdict": previous,
                "new_verdict": last_diagnosis.get("verdict"),
                "fit_ref": new_ref, "status": "executed",
            })
            tried_models.append(alternative)
            run.log(phase="retry", actor="ai" if run.plan_source.startswith("muse") else "deterministic",
                    status="ok", result_digest={"alternative": alternative},
                    decision="validated plan alternative selected")

        # 8. Grounded final interpretation -------------------------------
        verdict = last_diagnosis.get("verdict")
        reasons = [str(r) for r in (last_diagnosis.get("reasons") or [])]
        if verdict == PASS:
            state = DONE
        else:
            state = INSUFFICIENT_EVIDENCE
            if verdict in ("POOR_FIT", "FAILED"):
                reasons.append(
                    f"Attempt budget exhausted ({len(fit_refs)} fits, "
                    f"{len(run.retries)} retries); no model met the diagnostic thresholds."
                )
            if strategy == "halt_and_explain":
                reasons.append("The approved plan required halting rather than retrying.")
        evidence_refs = [seq for seq in (fit_seq.get(fit_refs[-1]) if fit_refs else None,
                                        diagnosis_seq) if seq]
        digest = run.digest_for_ai()
        conclusion = planner.deterministic_conclusion({**digest, "final": {"state": state,
                                                                          "retries": run.retries}})
        ai_report = None
        if self.config.use_ai:
            provider = self.config.interpretation_provider or planner.generate_grounded_interpretation
            try:
                ai_report = provider({**digest, "final": {"state": state}})
            except Exception as exc:
                ai_report = {"rejected": True, "error": type(exc).__name__}
        if ai_report and ai_report.get("rejected"):
            run.log(phase="interpret", actor="ai", status="rejected",
                    result_digest={"reason": "AI report failed grounding validation"},
                    decision="deterministic conclusion retained")
        run.finalize(state=state, conclusion=conclusion, evidence_refs=evidence_refs,
                     reasons=reasons, ai_report=ai_report)
        return run

    # ------------------------------------------------------------------
    def _acquire_plan(self, run: AgentRun, quality: dict) -> dict:
        """Obtain, validate, and fall back on a plan. Returns only accepted plans."""
        raw = None
        candidate_source = "deterministic_fallback"
        if self.config.use_ai:
            try:
                provider = self.config.plan_provider or planner.request_agent_plan
                raw = provider(quality)
                candidate_source = "muse_spark"
            except Exception as exc:
                run.log(phase="plan", actor="ai", status="unavailable",
                        result_digest={"error": type(exc).__name__},
                        decision="falling back to deterministic plan")
                raw = None
        if raw is None:
            raw = planner.deterministic_plan(quality)
            candidate_source = "deterministic_fallback"

        validation = planner.validate_plan(raw)
        run.log(phase="plan", actor="ai" if candidate_source == "muse_spark" else "deterministic",
                status="ok", result_digest={"plan": raw},
                decision="AI plan proposed" if candidate_source == "muse_spark"
                         else "deterministic plan generated")
        if not validation.accepted:
            run.log(phase="validate", actor="deterministic", status="rejected",
                    result_digest={"reasons": validation.reasons,
                                   "rejected_steps": validation.rejected_steps},
                    decision="plan rejected before any tool executed")
            raw = planner.deterministic_plan(quality)
            candidate_source = "deterministic_fallback_after_rejection"
            validation = planner.validate_plan(raw)
            run.log(phase="validate", actor="deterministic", status="ok",
                    result_digest={"reasons": validation.reasons},
                    decision="safe fallback plan validated")
        if not validation.accepted:  # pragma: no cover - defensive
            raise RuntimeError("the deterministic fallback plan failed validation")
        run.plan_validation = validation.as_dict()
        run.plan_source = candidate_source
        run.plan_hash = planner.plan_hash(validation.plan)
        run.log(phase="validate", actor="deterministic", status="ok",
                result_digest={"accepted": True, "steps": len(validation.plan["steps"])},
                decision=f"validated {candidate_source} plan")
        return validation.plan
