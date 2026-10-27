
"""Muse Spark (Baseten) adapter for evidence-grounded scientific reports.

The provider is optional: everything in ``analysis_core`` works without a
key. This module owns the *only* AI report schema, so the dashboard and the
CLI never drift apart. ``validate_report`` is deliberately strict because
its result is rendered, stored in the session and written into exports.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# Official Baseten Model API identifier documented by Meta and Baseten.
# Selected hackathon accounts may be told to use a dated variant; allow an
# override without changing code. Never put a key in this file.
MODEL = os.getenv("BASETEN_MODEL", "").strip() or "meta-models/muse-spark-open"
BASE_URL = "https://inference.baseten.co/v1"

REQUIRED_TITLES = (
    "Executive Summary",
    "Observed Pattern",
    "Model and Assumptions",
    "Quantitative Results",
    "Scientific Interpretation",
    "Uncertainty and Limitations",
    "Proposed Verification",
    "Conclusion",
)

# Registry of every section the report may contain. The eight titles in
# REQUIRED_TITLES remain the default set for full backward compatibility;
# callers may opt into any subset/superset of the ten registered titles.
SECTION_REGISTRY = {
    "Executive Summary": "One-paragraph summary of what was computed, grounded only in the supplied results.",
    "Observed Pattern": "Describe the pattern actually visible in the data and the fit diagnostics.",
    "Model and Assumptions": "State the chosen model and every assumption the user selected or the fit requires.",
    "Quantitative Results": "Quote computed coefficients, uncertainties and fit metrics with their units.",
    "Scientific Interpretation": "Interpret the results without claiming causation or unverified physical laws.",
    "Uncertainty and Limitations": "Distinguish statistical uncertainty, measurement uncertainty and model limitations.",
    "Proposed Verification": "Suggest concrete, testable follow-up measurements or checks.",
    "Conclusion": "A cautious conclusion that follows from the computed evidence.",
    "Data Quality and Cleaning": "Explain missing, invalid, non-finite and excluded observations and their likely effect.",
    "Alternative Explanations": "Offer competing mechanisms or confounders consistent with the same data.",
}
MAX_SECTIONS = len(SECTION_REGISTRY)
DEFAULT_SECTION_TITLES = REQUIRED_TITLES

# Hard limits. Everything crossing the provider boundary is untrusted input.
MAX_CLAIMS = 2
MAX_SECTION_WORDS = 25
MAX_TITLE_CHARS = 100
MAX_CONTENT_CHARS = 400
MAX_CLAIM_FIELD_CHARS = 600
MAX_RAW_REPORT_CHARS = 64_000
MAX_CONTEXT_CHARS = 32_000
MAX_PROMPT_CHARS = 48_000
MAX_COMPLETION_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 90.0

_CLAIM_FIELDS = (
    "claim",
    "evidence",
    "evidence_type",
    "confidence_or_uncertainty",
    "limitation",
    "proposed_verification",
)


def resolve_section_titles(section_titles=None):
    """Validate and canonicalize requested report section titles.

    ``None`` (the default) returns the legacy eight-title set. Requests must
    be a sequence of registered titles with no duplicates; unknown or
    unexpected names are rejected before anything reaches the provider.
    """
    if section_titles is None:
        return REQUIRED_TITLES
    if isinstance(section_titles, str) or not isinstance(section_titles, (list, tuple)):
        raise ValueError("Report sections must be a list of registered section titles.")
    if not 1 <= len(section_titles) <= MAX_SECTIONS:
        raise ValueError(f"Choose between 1 and {MAX_SECTIONS} report sections.")
    canonical = {title.casefold(): title for title in SECTION_REGISTRY}
    seen: set[str] = set()
    resolved: list[str] = []
    for title in section_titles:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Report section titles must be non-empty strings.")
        key = title.strip().casefold()
        if key not in canonical:
            raise ValueError(f"Unexpected report section: {title!r}.")
        if key in seen:
            raise ValueError(f"Duplicate report section: {title!r}.")
        seen.add(key)
        resolved.append(canonical[key])
    return tuple(resolved)


def build_prompt(analysis_context, section_titles=None):
    """Create a constrained, evidence-grounded scientific report prompt."""
    titles = resolve_section_titles(section_titles)
    sections = "\n".join(
        f"- {title}: {SECTION_REGISTRY[title]}" for title in titles
    )
    try:
        context = json.dumps(
            analysis_context,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "The analysis context could not be serialized for the AI request."
        ) from exc

    if len(context) > MAX_CONTEXT_CHARS:
        raise ValueError(
            "The analysis context is too large to send to the AI provider "
            f"({len(context):,} characters; limit {MAX_CONTEXT_CHARS:,}). "
            "Reduce the number of proposed measurements."
        )

    prompt = f"""
You are Muse Spark, an assistant for scientific experiment analysis.

Use only the supplied context for experimental facts and numerical results.
Never invent measurements, citations, uncertainty values, or experimental outcomes.
Separate computed results from interpretation and proposed hypotheses.
Explain limitations and avoid claiming correlation proves causation.

Return ONLY one valid JSON object, with no prose, no markdown code fences,
and no additional top-level keys:
{{
  "sections": [
    {{"title": "required section title", "content": "concise explanation"}}
  ],
  "claims": [
    {{
      "claim": "specific statement",
      "evidence": "supporting evidence from the supplied context",
      "evidence_type": "computed_result",
      "confidence_or_uncertainty": "uncertainty or confidence limitation",
      "limitation": "important limitation",
      "proposed_verification": "testable follow-up"
    }}
  ]
}}

Include each of these {len(titles)} sections exactly once, and no others:
{sections}

Limit each section's content to at most {MAX_SECTION_WORDS} words.
Include at most {MAX_CLAIMS} claims. Every claim must contain all six fields
as non-empty strings. If evidence is insufficient, explicitly say so rather
than inventing a conclusion.

Experiment context:
{context}
""".strip()

    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("The AI prompt exceeded the configured size limit.")
    return prompt


def validate_report(raw_report, section_titles=None):
    """Return a sanitized, schema-valid report dict, otherwise ``None``.

    This is the single source of truth for the report schema. The dashboard,
    exports and tests all consume its output. ``section_titles=None`` keeps
    the original eight-title default; any other request must be a validated
    subset of SECTION_REGISTRY. Extra keys supplied by the provider are
    discarded so untrusted AI output cannot smuggle arbitrary fields into
    the UI, session state or downloaded records.
    """
    if isinstance(raw_report, dict):
        report = raw_report
    elif isinstance(raw_report, str):
        candidate = raw_report.strip()

        if len(candidate) > MAX_RAW_REPORT_CHARS:
            return None

        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()

        try:
            report = json.loads(candidate)
        except (TypeError, json.JSONDecodeError, ValueError):
            return None
    else:
        return None

    if not isinstance(report, dict):
        return None

    try:
        titles = resolve_section_titles(section_titles)
    except ValueError:
        return None

    sections = report.get("sections")
    claims = report.get("claims")

    if not isinstance(sections, list) or not isinstance(claims, list):
        return None
    if len(sections) != len(titles) or len(claims) > MAX_CLAIMS:
        return None

    canonical = {title.casefold(): title for title in titles}
    seen = set()
    clean_sections = []

    for section in sections:
        if not isinstance(section, dict):
            return None

        title = section.get("title")
        content = section.get("content")

        if not isinstance(title, str) or not isinstance(content, str):
            return None
        if not title.strip() or not content.strip():
            return None
        if len(title) > MAX_TITLE_CHARS or len(content) > MAX_CONTENT_CHARS:
            return None
        if len(content.split()) > MAX_SECTION_WORDS:
            return None

        normalized = title.strip().casefold()
        if normalized not in canonical or normalized in seen:
            return None

        seen.add(normalized)
        clean_sections.append({
            "title": canonical[normalized],
            "content": content.strip(),
        })

    if seen != set(canonical):
        return None

    clean_claims = []
    for claim in claims:
        if not isinstance(claim, dict):
            return None
        if not set(_CLAIM_FIELDS).issubset(claim):
            return None

        values = {field: claim[field] for field in _CLAIM_FIELDS}
        if any(
            not isinstance(value, str)
            or not value.strip()
            or len(value) > MAX_CLAIM_FIELD_CHARS
            for value in values.values()
        ):
            return None

        clean_claims.append({field: value.strip() for field, value in values.items()})

    return {"sections": clean_sections, "claims": clean_claims}


def describe_provider_status(status):
    """Explain common HTTP failures without exposing credentials."""
    messages = {
        400: "Bad request (HTTP 400). The endpoint rejected a request parameter; check the configured model name.",
        401: "Authentication failed (HTTP 401). Check BASETEN_API_KEY in your local .env file.",
        403: "Access denied (HTTP 403). Check your account permissions and model access.",
        404: "Resource not found (HTTP 404). Check the configured model name and endpoint.",
        408: "Provider request timed out (HTTP 408). Retry later.",
        429: "Rate limit or quota reached (HTTP 429). Check your provider quota and retry later.",
        500: "Provider server error (HTTP 500). Retry later or check provider status.",
        502: "Provider gateway error (HTTP 502). Retry later or check provider status.",
        503: "Provider temporarily unavailable (HTTP 503). Retry later.",
        504: "Provider gateway timeout (HTTP 504). Retry later.",
    }
    if isinstance(status, int) and not isinstance(status, bool):
        return messages.get(
            status,
            f"Provider request failed (HTTP {status}). Check the endpoint, "
            "credentials, and provider logs.",
        )
    return (
        "Provider request failed. Check the endpoint, credentials, and "
        "provider logs."
    )


def _http_status(exc):
    """Return an integer HTTP status, or None when the field is unusable."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def _completion_request(client, prompt, *, json_mode, modern_tokens):
    """Issue one bounded chat-completion request.

    Meta's Model API prefers a ``developer`` instruction message over
    ``system`` and recommends leaving sampling at the provider default
    (temperature 1.0). JSON mode is requested when available because it
    makes a valid JSON object much more likely. ``modern_tokens`` selects
    ``max_completion_tokens`` (which budgets reasoning tokens) over the
    older ``max_tokens`` for compatibility with OpenAI-compatible gateways.
    """
    kwargs = {
        "model": MODEL,
        "messages": [
            {
                "role": "developer",
                "content": (
                    "You produce cautious scientific interpretations. "
                    "Return one valid JSON object only. Do not invent evidence."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    if modern_tokens:
        kwargs["max_completion_tokens"] = MAX_COMPLETION_TOKENS
    else:
        kwargs["max_tokens"] = MAX_COMPLETION_TOKENS
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return client.chat.completions.create(**kwargs)


def _network_error(exc):
    # Never display raw exception text: it may contain request headers or URLs.
    return RuntimeError(
        f"Could not contact the Muse Spark provider ({type(exc).__name__}). "
        "Check your connection, endpoint, credentials, and model access."
    )


def generate_interpretation(analysis_context, section_titles=None):
    """Request a Muse Spark report and return a validated wrapper.

    Returns ``{"model": str, "structured": {"sections": [...], "claims": [...]}}``.
    Raises ``ValueError`` for an unusable local context and ``RuntimeError``
    for provider failures; neither ever contains the API key.
    """
    # Validate the local report configuration first: a bad section request is
    # a caller error, not a missing-credential or provider failure.
    titles = resolve_section_titles(section_titles)
    prompt = build_prompt(analysis_context, titles)

    api_key = os.getenv("BASETEN_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "BASETEN_API_KEY is missing. Add it to the project's local .env file."
        )

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=1,
        )
    except Exception as exc:
        raise _network_error(exc) from None

    try:
        response = _completion_request(
            client, prompt, json_mode=True, modern_tokens=True
        )
    except Exception as exc:
        # Some OpenAI-compatible gateways reject response_format, the
        # developer role, or max_completion_tokens with HTTP 400. Retry once
        # with the most conservative request shape; never retry indefinitely.
        if _http_status(exc) != 400:
            status = _http_status(exc)
            if status is not None:
                raise RuntimeError(describe_provider_status(status)) from None
            raise _network_error(exc) from None
        try:
            response = _completion_request(
                client, prompt, json_mode=False, modern_tokens=False
            )
        except Exception as retry_exc:
            retry_status = _http_status(retry_exc)
            if retry_status is not None:
                raise RuntimeError(describe_provider_status(retry_status)) from None
            raise _network_error(retry_exc) from None

    choices = getattr(response, "choices", None)
    if not choices:
        raise RuntimeError("Muse Spark returned no response choices.")

    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        raise RuntimeError("Muse Spark returned a response without a message.")

    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        # Reasoning models can spend the whole token budget on thinking and
        # leave the visible answer empty. Report that clearly; never use
        # reasoning_content as a substitute for the structured report.
        extras = getattr(message, "model_extra", None) or {}
        if extras.get("reasoning_content"):
            raise RuntimeError(
                "Muse Spark returned reasoning but no visible report content. "
                "Increase the completion-token budget and try again."
            )
        raise RuntimeError("Muse Spark returned empty content.")

    if len(content) > MAX_RAW_REPORT_CHARS:
        raise RuntimeError(
            "Muse Spark returned an oversized response; it was rejected."
        )

    if getattr(choice, "finish_reason", None) == "length":
        raise RuntimeError(
            "Muse Spark's report was truncated before a complete JSON object. "
            "Increase the completion-token budget and try again."
        )

    structured = validate_report(content, titles)
    if structured is None:
        raise RuntimeError(
            "Muse Spark responded, but its report did not match the required "
            "JSON structure. Try again or inspect the model response format."
        )

    return {
        "model": getattr(response, "model", None) or MODEL,
        "structured": structured,
    }
