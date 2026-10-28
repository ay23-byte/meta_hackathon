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


def linear_prediction_intervals(fit, candidates) -> dict:
    """95% intervals for mean response and a single new observation, unweighted OLS.

    Uses the fitted X values and residuals, never an assumed instrument error.
    Prediction intervals require a future observation to share the same error model.
    """
    import numpy as np

    base = {
        "method": "Two-sided 95% Student-t intervals for unweighted linear regression",
        "assumptions": ASSUMPTIONS + " A future observation must have the same error variance and be independent.",
        "limitations": "Mean-response intervals are not individual prediction intervals. "
                       "Both are conditional on the model and error assumptions; they exclude X uncertainty, "
                       "systematic error and model selection. Extrapolation is especially unreliable.",
    }

    def unavailable(reason):
        return {**base, "status": "unavailable", "reason": reason, "rows": []}

    if not getattr(fit, "success", False) or getattr(fit, "model", None) != "linear":
        return unavailable("A successful linear fit is required.")
    if getattr(fit, "weighted", None) is not False:
        return unavailable("Intervals are not implemented for weighted fits.")
    try:
        x = np.asarray(fit.x_fit, dtype=float)
        residuals = np.asarray(fit.residuals, dtype=float)
        values = np.asarray(candidates, dtype=float)
    except (TypeError, ValueError):
        return unavailable("Finite fitted data and candidate X values are required.")
    n = getattr(fit, "n_observations", 0)
    if (x.ndim != 1 or residuals.ndim != 1 or values.ndim != 1 or
            len(x) != n or len(residuals) != n or n < 3 or not 0 < len(values) <= 50 or
            not np.all(np.isfinite(x)) or not np.all(np.isfinite(residuals)) or not np.all(np.isfinite(values))):
        return unavailable("At least three finite fit pairs and 1 to 50 finite candidate values are required.")
    try:
        slope = float(fit.parameters["slope"])
        intercept = float(fit.parameters["intercept"])
        with np.errstate(all="ignore"):
            xbar = float(np.mean(x))
            sxx = float(np.sum((x - xbar) ** 2))
            residual_variance = float(np.sum(residuals ** 2) / (n - 2))
            critical = float(t.ppf(0.975, n - 2))
            predicted = slope * values + intercept
            leverage = 1 / n + (values - xbar) ** 2 / sxx
            mean_margin = critical * np.sqrt(residual_variance * leverage)
            prediction_margin = critical * np.sqrt(residual_variance * (1 + leverage))
            lower_mean, upper_mean = predicted - mean_margin, predicted + mean_margin
            lower_prediction, upper_prediction = predicted - prediction_margin, predicted + prediction_margin
        if not all(math.isfinite(v) for v in (slope, intercept, xbar, sxx, residual_variance, critical)) or sxx <= 0:
            return unavailable("A finite, nonconstant fitted X range and finite residual variance are required.")
        if not all(np.all(np.isfinite(v)) for v in (predicted, lower_mean, upper_mean, lower_prediction, upper_prediction)):
            return unavailable("Interval calculation was nonfinite; check numerical range.")
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return unavailable("Fit parameters or interval inputs are invalid.")
    rows = [{"candidate_x": float(v), "predicted_y": float(p),
             "mean_lower": float(ml), "mean_upper": float(mu),
             "prediction_lower": float(pl), "prediction_upper": float(pu),
             "range_flag": "in_range" if x.min() <= v <= x.max() else "extrapolated"}
            for v, p, ml, mu, pl, pu in zip(values, predicted, lower_mean, upper_mean,
                                             lower_prediction, upper_prediction, strict=True)]
    return {**base, "status": "conditional", "reason": None,
            "degrees_of_freedom": n - 2, "rows": rows}
