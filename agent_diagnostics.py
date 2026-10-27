"""Deterministic diagnostics policy for the analysis agent.

Retry and stop decisions are computed here, from executed tool outputs, so
they are reproducible and testable. The planner may supply an ordered list of
validated fallback models, but it cannot change these thresholds.
"""

from __future__ import annotations

import re

import numpy as np

DEFAULT_RESEARCH_QUESTION = "How does the selected response Y vary with the selected X?"
MAX_RESEARCH_QUESTION_CHARS = 300

# A question is only actionable if it names a column or a testable quantity.
# This is a deliberately conservative, deterministic check; it never guesses
# what the user meant. Ambiguity always produces a clarification request.
_QUESTION_TOPICS = frozenset({
    "relationship", "correlation", "association", "effect", "change", "changes",
    "vary", "varies", "variation", "trend", "slope", "rate", "fit", "model",
    "compare", "comparison", "predict", "prediction", "resistance", "calibration",
    "sensitivity", "uncertainty", "outlier", "outliers", "quality", "linear",
    "nonlinear", "growth", "decay", "difference", "increase", "decrease",
    "response", "dependence", "dependent", "significance",
})
_VAGUE_PHRASES = (
    "is it good", "is this good", "what about it", "tell me something",
    "any insight", "what do you think", "does it matter", "is it significant",
    "analyze this", "analyse this", "make it better", "is it ok", "is it okay",
)

PASS = "PASS"
POOR_FIT = "POOR_FIT"
FAILED = "FAILED"
INSUFFICIENT = "INSUFFICIENT"

R2_MIN = 0.80
ADJUSTED_R2_MIN = 0.70
MIN_OBSERVATIONS = 4
MAX_INVALID_RATIO = 0.60
RUNS_LOW = 0.20
RUNS_HIGH = 0.80


def _fit_residuals(fit) -> np.ndarray:
    """Return residuals as an array; a NumPy array must never be used in `or`."""
    residuals = getattr(fit, "residuals", None)
    if residuals is None:
        return np.array([], dtype=float)
    return np.asarray(residuals, dtype=float).reshape(-1)


def residual_runs(residuals) -> dict:
    """Count residual sign changes to reveal systematic lack of fit."""
    values = np.asarray(residuals, dtype=float).reshape(-1)
    values = values[np.isfinite(values)]
    n = int(values.size)
    if n < 5:
        return {"n": n, "sign_changes": 0, "runs_ratio": None, "structured": False,
                "reason": "Too few finite residuals for a runs test."}
    # Exact synthetic fits leave ~1e-15 round-off residuals. Treating those
    # tiny values as sign changes would falsely flag a perfect fit.
    threshold = 1e-10 * max(float(np.max(np.abs(values))), 1.0)
    signs = np.sign(values[np.abs(values) > threshold])
    signs = signs[signs != 0]
    if signs.size < 5:
        return {"n": n, "sign_changes": 0, "runs_ratio": None, "structured": False,
                "reason": "Residuals are mostly zero."}
    changes = int(np.sum(signs[1:] != signs[:-1]))
    ratio = changes / (signs.size - 1)
    return {
        "n": n, "sign_changes": changes, "runs_ratio": round(float(ratio), 6),
        "structured": bool(ratio < RUNS_LOW or ratio > RUNS_HIGH),
        "reason": None,
    }


def diagnose_fit(fit, x=None, y=None) -> dict:
    """Classify one fitted model using only its computed metrics/residuals."""
    base = {"model": getattr(fit, "model", None), "verdict": None,
            "reasons": [], "r2": None, "adjusted_r2": None,
            "n_observations": getattr(fit, "n_observations", 0),
            "residual_runs": {}}
    if not getattr(fit, "success", False):
        base["verdict"] = FAILED
        base["reasons"].append(fit.reason or "The fit did not converge.")
        return base

    metrics = dict(getattr(fit, "metrics", {}) or {})
    r2 = metrics.get("r2")
    adj = metrics.get("adjusted_r2")
    n_params = int(metrics.get("n_parameters") or len(getattr(fit, "parameters", {})) or 1)
    n_obs = int(getattr(fit, "n_observations", 0) or 0)
    base.update({"r2": r2, "adjusted_r2": adj, "n_observations": n_obs})

    if r2 is None or n_obs < MIN_OBSERVATIONS or n_obs < n_params + 2:
        base["verdict"] = INSUFFICIENT
        base["reasons"].append(
            "R-squared is undefined or there are too few observations to leave "
            "a residual degree of freedom."
        )
        runs = residual_runs(_fit_residuals(fit))
        base["residual_runs"] = runs
        return base
    base["cautions"] = []
    if n_obs < 3 * (n_params + 1):
        base["cautions"].append(
            f"Only {n_obs} observations for {n_params} parameters; treat the fit as exploratory."
        )

    runs = residual_runs(_fit_residuals(fit))
    base["residual_runs"] = runs
    if r2 < R2_MIN:
        base["reasons"].append(f"R2 {r2:.4f} is below {R2_MIN:.2f}.")
    if adj is not None and adj < ADJUSTED_R2_MIN:
        base["reasons"].append(f"Adjusted R2 {adj:.4f} is below {ADJUSTED_R2_MIN:.2f}.")
    if runs.get("structured"):
        base["reasons"].append(
            f"Residual sign changes are non-random (ratio {runs.get('runs_ratio')})."
        )
    base["verdict"] = POOR_FIT if base["reasons"] else PASS
    if base["verdict"] == PASS:
        base["reasons"].append("Fit quality thresholds were met.")
    return base


def classify_quality(quality: dict) -> dict:
    """Decide whether the agent may proceed, must clarify, or must stop."""
    reasons: list[str] = []
    if quality.get("duplicate_headers"):
        return {
            "decision": "NEEDS_CLARIFICATION",
            "reasons": [f"Duplicate header names: {quality['duplicate_headers']}. "
                        "The user must choose which column is intended."],
            "recovery": [],
        }
    numeric = quality.get("numeric_columns") or []
    if len(numeric) < 2:
        return {
            "decision": "NEEDS_CLARIFICATION",
            "reasons": ["Fewer than two numeric columns were detected."],
            "recovery": [],
        }
    x, y = quality.get("suggested_x"), quality.get("suggested_y")
    ratios = quality.get("invalid_ratio") or {}
    for column in (x, y):
        if column and ratios.get(column, 0) > MAX_INVALID_RATIO:
            return {
                "decision": "NEEDS_CLARIFICATION",
                "reasons": [f"More than {MAX_INVALID_RATIO:.0%} of '{column}' is invalid; "
                            "the user must confirm the column choice."],
                "recovery": [],
            }
    n_pairs = int(quality.get("n_valid_pairs") or 0)
    if n_pairs < MIN_OBSERVATIONS:
        return {
            "decision": "INSUFFICIENT_EVIDENCE",
            "reasons": [f"Only {n_pairs} complete X/Y pairs remain; at least "
                        f"{MIN_OBSERVATIONS} are required."],
            "recovery": [],
        }
    recovery = []
    if quality.get("invalid") or quality.get("missing") or quality.get("nonfinite"):
        recovery.append(
            "Recover by using pairwise-complete numeric companion values for fitting; "
            "keep every original row in the cleaned dataset."
        )
        reasons.append(
            f"Data-quality issues detected: missing={quality.get('missing')}, "
            f"invalid={quality.get('invalid')}, nonfinite={quality.get('nonfinite')}."
        )
    if quality.get("ambiguous_roles"):
        reasons.append("Column roles are ambiguous; the plan must state X and Y explicitly.")
    return {"decision": "CONTINUE", "reasons": reasons, "recovery": recovery}


def choose_alternative(tried: list[str], fallback_models: list[str], max_attempts: int) -> str | None:
    """Pick the next validated, untried model; None when the budget is spent."""
    if len(tried) >= max_attempts:
        return None
    for model in fallback_models:
        if model not in tried:
            return model
    return None


def normalize_question(question: str | None) -> tuple[str, str]:
    """Return (question, source). Empty input uses an explicit generic default."""
    text = " ".join(str(question or "").split())[:MAX_RESEARCH_QUESTION_CHARS]
    if not text:
        return DEFAULT_RESEARCH_QUESTION, "default"
    return text, "user"


def clarify_question(question: str, columns=()) -> dict:
    """Decide whether the research question is too ambiguous to analyse.

    Returns ``{"needed", "reasons", "options"}``. Options are concrete,
    dataset-specific alternatives the user can select; the agent never invents
    the intended variable or conclusion.
    """
    text = " ".join(str(question or "").split())
    lowered = text.casefold()
    words = re.findall(r"[A-Za-z0-9_]+", lowered)
    column_names = [str(name) for name in (columns or []) if str(name).strip()]
    names_column = any(name.casefold() in lowered for name in column_names)
    has_topic = any(word in _QUESTION_TOPICS for word in words)
    vague = any(phrase in lowered for phrase in _VAGUE_PHRASES)
    needed = bool(len(text) < 8 or len(words) < 3 or vague
                  or (not names_column and not has_topic))
    x_name = column_names[0] if column_names else "the selected X column"
    y_name = column_names[1] if len(column_names) > 1 else "the selected Y column"
    options = [
        f"Estimate how {y_name} varies with {x_name}, and report the fitted equation and R².",
        f"Compare candidate models for {y_name} as a function of {x_name} and report diagnostics.",
        "Assess data quality first, then state whether the evidence supports any quantitative conclusion.",
    ]
    if not needed:
        return {"needed": False, "reasons": [], "options": []}
    reasons = [
        "The research question does not identify a measurable variable or a testable relationship.",
        "No analysis tool was executed: proceeding would require guessing the user's intent.",
    ]
    if vague:
        reasons.insert(0, "The question matches a known vague-phrase pattern.")
    return {"needed": True, "reasons": reasons, "options": options}
