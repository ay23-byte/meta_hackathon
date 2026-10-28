"""Small deterministic theory chapter for an explicitly confirmed Ohmic model.

This is not a general symbolic engine or an external-source retrieval system.
It never executes equations or infers a physical experiment from headers.
"""
from __future__ import annotations

import math

_CURRENT_SCALE = {"A": 1.0, "mA": 1e-3, "uA": 1e-6, "µA": 1e-6}
_VOLTAGE_SCALE = {"V": 1.0, "mV": 1e-3, "uV": 1e-6, "µV": 1e-6}


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def ohmic_chapter(result: dict, context: dict) -> dict:
    """Build an explicitly conditional chapter grounded in an existing result.

    Resistance conversion is derived from the authoritative fit slope, only
    for a successful linear model with explicitly confirmed current/voltage
    roles and recognized units. No physical assumption is validated by this.
    """
    if not context.get("confirmed_ohmic"):
        return {
            "status": "context_needed", "sections": [], "symbols": [], "derived": None,
            "missing": ["Confirm that X represents current and Y voltage and that an Ohmic model is appropriate."],
            "reference_status": "No external references retrieved or verified.",
        }

    roles = result.get("roles") or {}
    fit = result.get("fit") or {}
    x_unit, y_unit = roles.get("unit_x") or "", roles.get("unit_y") or ""
    current_scale, voltage_scale = _CURRENT_SCALE.get(x_unit), _VOLTAGE_SCALE.get(y_unit)
    sections = [
        {"title": "Introduction and model", "body": [
            "The user has chosen a conditional model for a current-voltage experiment; the uploaded data do not identify the apparatus or prove the model.",
            "An approximately Ohmic element has voltage proportional to current over a range in which relevant physical conditions remain sufficiently stable.",
        ]},
        {"title": "Assumptions and derivation", "body": [
            "Assume the measured X represents current I, measured Y represents voltage V, and the ratio V/I is constant over the range of interest.",
            "For I ≠ 0 define R = V/I. Multiply both sides by I to obtain V = R I. At I = 0 the ratio is undefined; V = 0 follows only by extending the assumed linear model to zero.",
            "For a practical regression write V = a I + b. If the assumptions and units hold, a estimates resistance; b is a fitted voltage intercept, not an identified physical mechanism.",
            "This is an algebraic consequence of the stated proportionality, not a derivation from microscopic material physics and not experimental proof of Ohm's law.",
        ]},
        {"title": "Units and dimensional check", "body": [
            "V is measured in volts, I in amperes and resistance R in ohms. One ohm equals one volt per ampere, so RI has units of volts.",
            "If the axes use prefixes, multiply the numerical slope by (voltage unit in volts)/(current unit in amperes) to obtain ohms; a fitted intercept remains in the Y-axis voltage units.",
        ]},
        {"title": "Illustrative worked example — not user data", "body": [
            "For illustration only: if V = 2 V at I = 0.5 A and the stated model is valid, R = 2 V / 0.5 A = 4 ohms. These are not measurements from the uploaded file.",
        ]},
        {"title": "Interpretation and limitations", "body": [
            "Compare the fitted curve and residuals over the measured range; outside it, predictions are extrapolations. A high R² describes fit quality, not causation or universal model validity.",
            "An intercept may reflect multiple possibilities, but its cause cannot be identified from this fit alone. Conditions, calibration, material and measurement uncertainty require independent information.",
            "Repeat measurements under documented conditions, examine residuals and assess calibrated uncertainties before drawing stronger conclusions.",
        ]},
    ]
    level = context.get("level", "beginner")
    level_note = {
        "beginner": "Intuition: the slope says how much voltage changes for each unit change in current; the offset is the extrapolated value at zero current.",
        "intermediate": "For the fitted line, the slope has units of voltage per current; a nonzero fitted offset is descriptive and does not identify its cause.",
        "undergraduate": "Least-squares slope and intercept summarize the chosen sample. Residual patterns can indicate model mismatch but do not identify a mechanism.",
        "advanced": "Least-squares uncertainty depends on the assumed error model; systematic effects and current-axis measurement errors require separate analysis.",
        "postgraduate": "Assess the residual structure, weighting assumptions, parameter covariance and potential errors in both axes before treating the fit as a precise resistance estimate.",
        "research": "Check model identifiability, calibration traceability, residual dependence, uncertainty in both axes and the range over which conditions remain stable; independent replication is required.",
    }.get(level)
    if level_note:
        sections[-1]["body"].append(level_note)
    symbols = [
        {"symbol": "I", "meaning": "current, user-selected X", "unit": x_unit or "unknown", "origin": "user-selected measurement"},
        {"symbol": "V", "meaning": "voltage, user-selected Y", "unit": y_unit or "unknown", "origin": "user-selected measurement"},
        {"symbol": "R", "meaning": "conditional resistance", "unit": "ohm", "origin": "theory assumption / derived"},
        {"symbol": "a", "meaning": "fitted slope", "unit": f"{y_unit or '?'} per {x_unit or '?'}", "origin": "computed fit"},
        {"symbol": "b", "meaning": "fitted intercept", "unit": y_unit or "unknown", "origin": "computed fit"},
    ]
    missing = []
    derived = None
    if current_scale is None or voltage_scale is None:
        missing.append("Recognized current and voltage units are required for resistance in ohms.")
    if not fit.get("success") or fit.get("model") != "linear":
        missing.append("A successful linear fit is required to interpret its slope as resistance.")
    slope = (fit.get("parameters") or {}).get("slope")
    if fit.get("success") and fit.get("model") == "linear" and not _finite_number(slope):
        missing.append("A finite fitted slope is required for resistance conversion.")
    if not missing:
        factor = voltage_scale / current_scale
        value = slope * factor
        if math.isfinite(value):
            derived = {"name": "conditional resistance from fitted slope", "value": value,
                       "unit": "ohm", "conversion_factor": factor,
                       "source": "fit.parameters.slope and user-selected axis units",
                       "status": "model_based_not_independently_verified"}
        else:
            missing.append("Resistance conversion is non-finite and was not reported.")
    return {
        "status": "conditional_user_confirmed", "sections": sections, "symbols": symbols,
        "derived": derived, "missing": missing,
        "reference_status": "No external references retrieved or verified; human review is required.",
        "completeness": {"identified_theory": "user_confirmed_assumption", "units": "available" if current_scale is not None and voltage_scale is not None else "missing_or_unsupported",
                         "derivation": "conditional_algebra_only", "literature": "not_verified",
                         "apparatus_and_conditions": "user_supplied_or_unknown", "validation": "not_experimental_proof"},
    }
