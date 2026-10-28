"""Conditional confidence intervals for an existing unweighted linear fit.

This does not estimate instrument uncertainty or validate the error model.
"""
from __future__ import annotations

import math

from scipy.stats import t

ASSUMPTIONS = (
    "Conditional on the selected linear model, independent normally distributed "
    "errors with constant variance and effectively fixed X. These assumptions "
    "are not verified by the interval."
)
LIMITATIONS = (
    "Parameter confidence intervals describe sampling uncertainty under the stated model; "
    "they do not include calibration error, X measurement uncertainty, systematic bias "
    "or model-selection uncertainty. They are not prediction intervals."
)


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def linear_parameter_intervals(fit: dict | None, roles: dict | None = None) -> dict:
    """Return 95% Student-t intervals, or explain why they are unavailable."""
    fit, roles = fit or {}, roles or {}
    base = {"method": "Student-t interval using residual standard errors",
            "confidence_level": 0.95, "assumptions": ASSUMPTIONS, "limitations": LIMITATIONS}

    def unavailable(reason):
        return {**base, "status": "unavailable", "reason": reason, "parameters": []}

    if not fit.get("success") or fit.get("model") != "linear":
        return unavailable("A successful linear fit is required.")
    if fit.get("weighted") is not False:
        return unavailable("Intervals are not implemented for weighted or unspecified-weight fits.")
    dof = (fit.get("metrics") or {}).get("degrees_of_freedom")
    n = fit.get("n_observations")
    if not isinstance(n, int) or isinstance(n, bool) or not isinstance(dof, int) or isinstance(dof, bool) or dof != n - 2 or dof <= 0:
        return unavailable("At least three observations and positive residual degrees of freedom are required.")
    params, errors = fit.get("parameters") or {}, fit.get("parameter_errors") or {}
    if not all(_finite_number(params.get(k)) and _finite_number(errors.get(k)) and errors[k] >= 0
               for k in ("slope", "intercept")):
        return unavailable("Finite parameter estimates and residual standard errors are required.")
    critical = float(t.ppf(0.975, dof))
    if not math.isfinite(critical):
        return unavailable("The Student-t critical value is not finite.")
    ux, uy = roles.get("unit_x") or "", roles.get("unit_y") or ""
    units = {"slope": f"{uy}/{ux}" if ux and uy else "unspecified",
             "intercept": uy or "unspecified"}
    intervals = []
    for name in ("slope", "intercept"):
        estimate, se = params[name], errors[name]
        low, high = estimate - critical * se, estimate + critical * se
        if not math.isfinite(low) or not math.isfinite(high):
            return unavailable("The calculated confidence interval is nonfinite.")
        intervals.append({"parameter": name, "estimate": estimate, "standard_error": se,
                          "lower": low, "upper": high, "unit": units[name],
                          "evidence": [f"fit.parameters.{name}", f"fit.parameter_errors.{name}",
                                       "fit.metrics.degrees_of_freedom"]})
    return {**base, "status": "conditional", "reason": None,
            "degrees_of_freedom": dof, "critical_value": critical, "parameters": intervals}


def propagate_independent(operation: str, a: float, u_a: float, unit_a: str,
                          b: float, u_b: float, unit_b: str, *, confirmed: bool) -> dict:
    """Propagate user-supplied standard uncertainties through four operations.

    First-order derivatives assume zero covariance; no expression is evaluated.
    """
    if not confirmed:
        raise ValueError("Confirm both entered values and their standard uncertainties.")
    if operation not in ("sum", "difference", "product", "ratio"):
        raise ValueError("Unsupported operation.")
    if not all(_finite_number(value) for value in (a, u_a, b, u_b)) or u_a < 0 or u_b < 0:
        raise ValueError("Values and nonnegative standard uncertainties must be finite numbers.")
    if not isinstance(unit_a, str) or not isinstance(unit_b, str):
        raise ValueError("Enter units for both input quantities.")
    unit_a, unit_b = unit_a.strip(), unit_b.strip()
    if not unit_a or not unit_b or len(unit_a) > 24 or len(unit_b) > 24:
        raise ValueError("Enter units for both input quantities (use 1 for dimensionless).")
    if operation in ("sum", "difference") and unit_a != unit_b:
        raise ValueError("Addition and subtraction require identical units; no unit conversion is performed.")
    if operation == "ratio" and b == 0:
        raise ValueError("The denominator must not be zero.")
    if operation == "sum":
        value, term_a, term_b, unit, equation = a + b, u_a, u_b, unit_a, "z = a + b"
    elif operation == "difference":
        value, term_a, term_b, unit, equation = a - b, u_a, u_b, unit_a, "z = a - b"
    elif operation == "product":
        value, term_a, term_b, unit, equation = a * b, b * u_a, a * u_b, f"({unit_a})·({unit_b})", "z = a * b"
    else:
        # This form avoids squaring b, reducing avoidable overflow/underflow.
        value = a / b
        term_a, term_b = u_a / b, (value / b) * u_b
        unit, equation = f"({unit_a})/({unit_b})", "z = a / b"
    uncertainty = math.hypot(term_a, term_b)
    if not math.isfinite(value) or not math.isfinite(uncertainty):
        raise ValueError("The result or propagated uncertainty is nonfinite; check the input magnitudes.")
    warning = ("The denominator is within three standard uncertainties of zero; "
               "first-order propagation can be unreliable for ratios."
               if operation == "ratio" and u_b > 0 and abs(b) <= 3 * u_b else None)
    return {
        "status": "conditional_user_supplied", "operation": operation, "equation": equation,
        "inputs": {"a": a, "u_a": u_a, "unit_a": unit_a, "b": b, "u_b": u_b, "unit_b": unit_b},
        "value": value, "standard_uncertainty": uncertainty, "unit": unit,
        "method": "First-order independent-input propagation: u(z) = sqrt((dz/da * u(a))² + (dz/db * u(b))²).",
        "assumptions": "Inputs are user-supplied standard uncertainties in the same units as their values; covariance is assumed zero. First-order approximation is used.",
        "limitations": "Not a confidence or prediction interval; systematic effects, covariance and higher-order terms are not assessed. Unit labels are user supplied and not dimensionally validated.",
        "warning": warning,
    }
