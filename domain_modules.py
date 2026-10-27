"""Optional, *explicitly selected* scientific interpretation layers.

The default is ``generic``: no physical law, constant, or unit is assumed.
A domain module may only report a named physical quantity when the user has
selected that module AND supplied units that justify it. Nothing here infers
a domain from a filename, a column name, or a fitted coefficient.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DOMAIN_GENERIC = "generic"
DOMAIN_OHMIC = "ohmic"
DOMAIN_CALIBRATION = "calibration"
DOMAIN_GROWTH = "growth"


@dataclass
class DomainModule:
    id: str
    label: str
    description: str
    assumptions: list[str] = field(default_factory=list)
    required_roles: tuple[str, ...] = ("x", "y")

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "assumptions": list(self.assumptions),
            "required_roles": list(self.required_roles),
        }


DOMAIN_MODULES: dict[str, DomainModule] = {
    DOMAIN_GENERIC: DomainModule(
        id=DOMAIN_GENERIC,
        label="Generic / no domain assumption",
        description="Report only statistics and fitted coefficients. No physical law is assumed.",
        assumptions=["The selected X and Y columns are the variables the user wants to relate."],
    ),
    DOMAIN_OHMIC: DomainModule(
        id=DOMAIN_OHMIC,
        label="Ohmic conductor (explicit choice)",
        description=(
            "Interpret a linear slope as electrical resistance ONLY when X is current "
            "and Y is voltage and the user supplies matching units."
        ),
        assumptions=[
            "The user explicitly selected the Ohmic interpretation.",
            "X represents electric current and Y represents potential difference.",
            "The device is approximately ohmic over the measured range (constant temperature, no threshold).",
            "A linear model with an intercept near zero is appropriate; a non-zero intercept may indicate an offset.",
            "Units supplied by the user are A for X and V for Y (or a consistently scaled pair such as mA/mV).",
        ],
        required_roles=("x", "y"),
    ),
    DOMAIN_CALIBRATION: DomainModule(
        id=DOMAIN_CALIBRATION,
        label="Linear calibration curve",
        description="Treat the linear slope as instrument sensitivity for inverse prediction.",
        assumptions=[
            "X is a known reference/standard value and Y is the instrument response.",
            "The calibration is linear over the measured range only.",
            "Reference X uncertainty is negligible compared with Y uncertainty.",
        ],
        required_roles=("x", "y"),
    ),
    DOMAIN_GROWTH: DomainModule(
        id=DOMAIN_GROWTH,
        label="Exponential growth / decay",
        description="Convert an exponential rate into a doubling or half-life time.",
        assumptions=[
            "The fitted model is y = A*exp(k*x) + C with an additive offset C.",
            "X is elapsed time in the stated unit and is uniformly spaced in that unit.",
            "The mechanism remains exponential beyond the observed range (unverified).",
        ],
        required_roles=("x", "y"),
    ),
}


def list_domain_modules() -> list[dict]:
    return [module.as_dict() for module in DOMAIN_MODULES.values()]


def _unit_ok(unit: str, accepted: tuple[str, ...]) -> bool:
    normalized = str(unit or "").strip().replace(" ", "")
    return normalized.casefold() in {item.casefold() for item in accepted}


def apply_domain(module_id: str, fit_result, config: dict) -> dict:
    """Return computed quantities plus clearly labelled hypotheses.

    ``fit_result`` is a ``fitting_core.FitResult`` (or any object exposing
    ``success``, ``parameters``, ``parameter_errors``, ``metrics``, ``model``).
    The result is designed to be embedded verbatim in the AI context and the
    Markdown report, so it separates computed values from interpretation.
    """
    module = DOMAIN_MODULES.get(module_id, DOMAIN_MODULES[DOMAIN_GENERIC])
    result = {
        "module": module.id,
        "label": module.label,
        "description": module.description,
        "assumptions": list(module.assumptions),
        "computed": {},
        "derived": [],
        "hypotheses": [],
        "warnings": [],
        "fit_success": bool(getattr(fit_result, "success", False)),
    }
    if not result["fit_success"]:
        result["warnings"].append(
            "No successful fit is available, so no domain-specific quantity was computed."
        )
        return result

    params = dict(getattr(fit_result, "parameters", {}) or {})
    errors = dict(getattr(fit_result, "parameter_errors", {}) or {})
    model = getattr(fit_result, "model", None)
    x_label = str(config.get("x_label") or config.get("x") or "X")
    y_label = str(config.get("y_label") or config.get("y") or "Y")
    unit_x = str(config.get("unit_x") or "")
    unit_y = str(config.get("unit_y") or "")
    unit_time = str(config.get("unit_time") or unit_x)

    if module.id == DOMAIN_GENERIC:
        result["computed"] = {
            "model": model,
            "parameters": params,
            "x": x_label,
            "y": y_label,
        }
        result["warnings"].append(
            "Generic mode: coefficients are in the units of the selected columns; "
            "no physical constant has been named or inferred."
        )
        return result

    if module.id == DOMAIN_OHMIC:
        if model != "linear":
            result["warnings"].append("Ohmic resistance is only defined here for a linear fit; no value was reported.")
            return result
        slope = params.get("slope")
        slope_error = errors.get("slope")
        result["computed"] = {
            "slope": slope,
            "slope_error": slope_error,
            "intercept": params.get("intercept"),
            "x": x_label,
            "y": y_label,
            "unit_x": unit_x,
            "unit_y": unit_y,
        }
        units_valid = _unit_ok(unit_x, ("A", "mA", "µA", "uA")) and _unit_ok(unit_y, ("V", "mV", "µV", "uV"))
        if not units_valid:
            result["warnings"].append(
                "Units were not a recognised current/voltage pair, so the slope is reported only as a "
                "proportionality coefficient. Supply X units of A (or mA/µA) and Y units of V (or mV/µV) "
                "to request resistance in ohms."
            )
            result["derived"].append({
                "name": "proportionality coefficient (unnamed)",
                "value": slope,
                "unit": f"{unit_y or 'Y units'} per {unit_x or 'X unit'}",
                "source": "linear fit slope",
            })
            return result
        # mA/mV and µA/µV pairs cancel to give ohms; mixed prefixes would not.
        prefix_x = {"a": 1.0, "ma": 1e-3, "µa": 1e-6, "ua": 1e-6}.get(unit_x.strip().casefold(), 1.0)
        prefix_y = {"v": 1.0, "mv": 1e-3, "µv": 1e-6, "uv": 1e-6}.get(unit_y.strip().casefold(), 1.0)
        factor = prefix_y / prefix_x
        resistance = slope * factor if slope is not None else None
        resistance_error = slope_error * factor if slope_error is not None else None
        result["derived"].append({
            "name": "electrical resistance (candidate)",
            "value": resistance,
            "error": resistance_error,
            "unit": "ohm",
            "source": "linear fit slope with user-supplied current/voltage units",
        })
        result["hypotheses"].append(
            "HYPOTHESIS (not verified): under the explicitly selected Ohmic assumption, "
            f"the slope corresponds to R = {resistance:.6g} ohm. This is a model-based "
            "interpretation, not a direct measurement of resistance."
        )
        result["warnings"].append(
            "Ohm's law is an assumption chosen by the user, not a conclusion derived from the fit. "
            "A non-zero intercept, heating, or a non-linear region would invalidate it."
        )
        return result

    if module.id == DOMAIN_CALIBRATION:
        if model != "linear":
            result["warnings"].append("Calibration sensitivity is only reported for a linear fit.")
            return result
        slope, intercept = params.get("slope"), params.get("intercept")
        result["computed"] = {"slope": slope, "intercept": intercept, "x": x_label, "y": y_label}
        result["derived"].append({
            "name": "sensitivity",
            "value": slope,
            "unit": f"{unit_y or 'Y units'} per {unit_x or 'X unit'}",
            "source": "linear fit slope",
        })
        if slope not in (None, 0) and intercept is not None:
            result["derived"].append({
                "name": "inverse-prediction formula",
                "value": None,
                "unit": None,
                "source": f"X_estimated = (Y - ({intercept:.6g})) / ({slope:.6g}); valid only within the fitted range",
            })
        result["warnings"].append(
            "Inverse prediction ignores uncertainty in the reference values and is valid only inside the calibrated range."
        )
        return result

    # Growth / decay
    if model != "exponential":
        result["warnings"].append("Doubling/half-life is only defined for a fitted exponential model.")
        return result
    rate = params.get("rate")
    result["computed"] = {"rate": rate, "amplitude": params.get("amplitude"),
                          "offset": params.get("offset"), "time_unit": unit_time}
    if isinstance(rate, (int, float)) and math.isfinite(rate) and abs(rate) > 1e-15:
        characteristic = math.log(2) / abs(rate)
        name = "doubling time" if rate > 0 else "half-life"
        result["derived"].append({
            "name": name,
            "value": characteristic,
            "unit": unit_time or "X unit",
            "source": "ln(2) / |rate| from the fitted exponential",
        })
        result["hypotheses"].append(
            f"HYPOTHESIS (not verified): if the exponential mechanism persists, the {name} "
            f"is {characteristic:.6g} {unit_time or 'X units'}."
        )
    result["warnings"].append(
        "An additive offset C was fitted; a non-zero baseline changes the interpretation of the rate."
    )
    return result
