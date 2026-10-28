"""Offline, evidence-labelled research notes derived from the current result.

No network access or inference of a scientific domain from column names.
Numerical values are referenced from the authoritative result at render time.
"""
from __future__ import annotations

LEVELS = ("beginner", "intermediate", "advanced", "undergraduate", "postgraduate", "research")


def experiment_context(*, title="", discipline="", description="", apparatus="",
                       conditions="", known_equation="", level="beginner",
                       confirmed_ohmic=False):
    """Capture bounded user-supplied metadata, never infer an experiment."""
    if level not in LEVELS:
        raise ValueError("Explanation level is not supported.")
    return {
        "title": str(title).strip()[:300], "discipline": str(discipline).strip()[:100],
        "description": str(description).strip()[:1000], "apparatus": str(apparatus).strip()[:500],
        "conditions": str(conditions).strip()[:500], "known_equation": str(known_equation).strip()[:300],
        "level": level, "confirmed_ohmic": bool(confirmed_ohmic),
        "provenance": "user_supplied_not_verified",
    }


def theory_notes(result, context):
    """Return structured text; the supplied result remains the source of numbers."""
    roles = result.get("roles") or {}
    fit = result.get("fit") or {}
    notes = [
        "The dataset and column roles are user-selected; experimental identity and provenance are not independently verified.",
        "A fitted association does not establish a physical mechanism or causation.",
    ]
    if not context.get("confirmed_ohmic"):
        notes.append("No physical theory has been confirmed. Supply experiment context and select a theory explicitly before interpreting a coefficient as a physical quantity.")
        return {"status": "context_needed", "notes": notes, "references": []}
    notes += [
        "User-confirmed model assumption: voltage V and current I may be related by V = I R for an approximately ohmic conductor under stable conditions.",
        "For I ≠ 0, resistance is defined as R = V / I; multiplying by I gives V = I R. This algebra does not establish that the sample is ohmic.",
        "A fitted line V = a I + b allows an intercept; a estimates resistance only when X is current, Y is voltage and units are compatible. The cause of a nonzero intercept is not established by this fit.",
    ]
    if roles.get("unit_x") not in ("A", "mA", "µA", "uA") or roles.get("unit_y") not in ("V", "mV", "µV", "uV"):
        notes.append("Current and voltage units are missing or unrecognised; do not interpret the slope as resistance until they are confirmed.")
    if not fit.get("success") or fit.get("model") != "linear":
        notes.append("The selected fit is not a successful linear fit; no resistance interpretation is supplied.")
    notes.append("A high R² is not proof of Ohm's law. Inspect residuals, measurement uncertainties and stability; collect independent repeat measurements.")
    if context.get("level") == "beginner":
        notes.append("The slope describes the change in voltage per change in current; the intercept is the fitted voltage at zero current.")
    elif context.get("level") == "advanced":
        notes.append("Parameter precision from residual scatter depends on the model and error assumptions; systematic error and uncertainty in current are not established here.")
    return {"status": "user_confirmed_assumption", "notes": notes, "references": [],
            "reference_status": "External references not retrieved or verified."}


def reliability_notes(result):
    """Summarize available diagnostics without fabricating instrument accuracy."""
    fit = result.get("fit") or {}
    roles = result.get("roles") or {}
    notes = [
        "Independence, instrument accuracy, calibration and systematic error cannot be established from the data alone.",
        "Outlier flags are diagnostics, not proof of an erroneous measurement; no outliers are removed automatically.",
        "Fit parameter errors, when present, depend on model and residual assumptions and are not instrument accuracy.",
    ]
    if fit.get("weighted"):
        notes.append("The fit used supplied weights; their inverse-variance interpretation depends on valid, calibrated 1-sigma uncertainties.")
    elif roles.get("uncertainty"):
        notes.append("An uncertainty column was selected but the current fit is unweighted; inspect validation warnings before using it.")
    else:
        notes.append("No measurement uncertainty was supplied for the fit; none has been invented.")
    n = fit.get("n_observations")
    if isinstance(n, int) and n < 10:
        notes.append("The fitted sample is small; evaluate sensitivity and collect additional independent measurements where feasible.")
    if not fit.get("success"):
        notes.append("The selected fit did not succeed; parameter reliability cannot be assessed.")
    return {"status": "deterministic_diagnostics", "notes": notes}
