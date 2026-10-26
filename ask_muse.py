
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODEL = "meta-models/muse-spark-open"
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


def build_prompt(analysis_context):
    """Create a constrained, evidence-grounded scientific report prompt."""
    sections = "\n".join(f"- {title}" for title in REQUIRED_TITLES)
    context = json.dumps(
        analysis_context,
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )

    return f"""
You are Muse Spark, an assistant for scientific experiment analysis.

Use only the supplied context for experimental facts and numerical results.
Never invent measurements, citations, uncertainty values, or experimental outcomes.
Separate computed results from interpretation and proposed hypotheses.
Explain limitations and avoid claiming correlation proves causation.

Return ONLY a valid JSON object with this structure:
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

Include each of these eight sections exactly once:
{sections}

Limit each section's content to at most 25 words.
Include at most two claims. Every claim must contain all six fields.
If evidence is insufficient, explicitly say so rather than inventing a conclusion.

Experiment context:
{context}
""".strip()


def validate_report(raw_report):
    """Return a valid structured report dictionary, otherwise None."""
    if isinstance(raw_report, dict):
        report = raw_report
    elif isinstance(raw_report, str):
        candidate = raw_report.strip()

        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()

        try:
            report = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            return None
    else:
        return None

    if not isinstance(report, dict):
        return None

    sections = report.get("sections")
    claims = report.get("claims")

    if not isinstance(sections, list) or not isinstance(claims, list):
        return None

    if len(sections) != len(REQUIRED_TITLES) or len(claims) > 2:
        return None

    expected = {title.casefold() for title in REQUIRED_TITLES}
    seen = set()

    for section in sections:
        if not isinstance(section, dict):
            return None

        title = section.get("title")
        content = section.get("content")

        if not isinstance(title, str) or not isinstance(content, str):
            return None

        normalized = title.strip().casefold()
        if normalized not in expected or normalized in seen:
            return None

        if len(content.split()) > 25:
            return None

        seen.add(normalized)

    if seen != expected:
        return None

    required_fields = {
        "claim",
        "evidence",
        "evidence_type",
        "confidence_or_uncertainty",
        "limitation",
        "proposed_verification",
    }

    for claim in claims:
        if not isinstance(claim, dict):
            return None

        if not required_fields.issubset(claim):
            return None

        if any(
            not isinstance(claim[field], str) or not claim[field].strip()
            for field in required_fields
        ):
            return None

    return report


def describe_provider_status(status):
    """Explain common HTTP failures without exposing credentials."""
    messages = {
        401: "Authentication failed (HTTP 401). Check BASETEN_API_KEY in your local .env file.",
        403: "Access denied (HTTP 403). Check your account permissions and model access.",
        404: "Resource not found (HTTP 404). Check the configured model name and endpoint.",
        429: "Rate limit or quota reached (HTTP 429). Check your provider quota and retry later.",
    }
    return messages.get(
        status,
        f"Provider request failed (HTTP {status}). Check the endpoint, credentials, and provider logs.",
    )


def generate_interpretation(analysis_context):
    """
    Request a Muse Spark report.

    Returns the wrapper expected by app.py:
    {
        "model": "...",
        "structured": {"sections": [...], "claims": [...]}
    }
    """
    api_key = os.getenv("BASETEN_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "BASETEN_API_KEY is missing. Add it to the project's local .env file."
        )

    client = OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
        timeout=90.0,
        max_retries=1,
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You produce cautious scientific interpretations. "
                        "Return valid JSON only and do not invent evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": build_prompt(analysis_context),
                },
            ],
            stream=False,
            temperature=0.2,
            max_tokens=2500,
        )
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status is not None:
            raise RuntimeError(describe_provider_status(status)) from None

        # Avoid displaying raw exception text because it may contain
        # request details. The app can safely show this generic message.
        raise RuntimeError(
            f"Could not contact the Muse Spark provider ({type(exc).__name__}). "
            "Check your connection, endpoint, credentials, and model access."
        ) from None

    if not response.choices:
        raise RuntimeError("Muse Spark returned no response choices.")

    message = response.choices[0].message
    content = message.content

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Muse Spark returned empty content.")

    structured = validate_report(content)
    if structured is None:
        raise RuntimeError(
            "Muse Spark responded, but its report did not match the required "
            "JSON structure. Try again or inspect the model response format."
        )

    return {
        "model": getattr(response, "model", None) or MODEL,
        "structured": structured,
    }
