"""Flexible, explicit curve fitting.

No model is assumed by default. Each model is fitted only on the caller's
complete finite pairs; failures are returned as structured reasons rather
than tracebacks; predictions outside the fitted X range are flagged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.polynomial import Polynomial
from scipy.optimize import curve_fit


def format_si(value: float, precision: int = 6) -> str:
    """Compact numeric formatting without implying any physical unit."""
    if not np.isfinite(value):
        return "nan"
    if value == 0:
        return "0"
    if abs(value) >= 1e5 or abs(value) < 1e-3:
        return f"{value:.{precision - 1}e}"
    return f"{value:.{precision}g}"

MODEL_LINEAR = "linear"
MODEL_POLYNOMIAL = "polynomial"
MODEL_EXPONENTIAL = "exponential"
MODEL_LOGARITHMIC = "logarithmic"
MODEL_POWER = "power"

MODEL_SPECS = {
    MODEL_LINEAR: {
        "label": "Linear  y = a*x + b",
        "assumptions": "A straight-line relationship over the observed range.",
        "extra": [],
    },
    MODEL_POLYNOMIAL: {
        "label": "Polynomial  y = sum(c_k * x^k)",
        "assumptions": "Smooth polynomial trend; high degrees can overfit and extrapolate badly.",
        "extra": ["degree"],
    },
    MODEL_EXPONENTIAL: {
        "label": "Exponential  y = A*exp(k*x) + C",
        "assumptions": "Exponential growth/decay with an additive offset; A must be positive by construction.",
        "extra": [],
    },
    MODEL_LOGARITHMIC: {
        "label": "Logarithmic  y = A*ln(x) + C",
        "assumptions": "Requires strictly positive X values.",
        "extra": [],
    },
    MODEL_POWER: {
        "label": "Power  y = A*x^k",
        "assumptions": "Requires strictly positive X and positive Y values.",
        "extra": [],
    },
}


@dataclass
class FitResult:
    model: str
    label: str
    success: bool
    parameters: dict[str, float] = field(default_factory=dict)
    parameter_errors: dict[str, float] = field(default_factory=dict)
    equation: str = ""
    metrics: dict = field(default_factory=dict)
    assumptions: str = ""
    warnings: list[str] = field(default_factory=list)
    residuals: np.ndarray | None = None
    x_fit: np.ndarray | None = None
    n_observations: int = 0
    n_excluded: int = 0
    weighted: bool = False
    x_range: tuple[float, float] | None = None
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "label": self.label,
            "success": self.success,
            "parameters": self.parameters,
            "parameter_errors": self.parameter_errors,
            "equation": self.equation,
            "metrics": self.metrics,
            "assumptions": self.assumptions,
            "warnings": list(self.warnings),
            "n_observations": self.n_observations,
            "n_excluded": self.n_excluded,
            "weighted": self.weighted,
            "x_range": list(self.x_range) if self.x_range else None,
            "reason": self.reason,
        }


def _prepare_pairs(x, y, weights=None) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    raw_x = pd_to_numeric(x)
    raw_y = pd_to_numeric(y)
    n_total = len(raw_x)
    raw_w = (
        np.ones(n_total, dtype=float)
        if weights is None
        else pd_to_numeric(weights)
    )
    mask = np.isfinite(raw_x) & np.isfinite(raw_y) & np.isfinite(raw_w) & (raw_w > 0)
    return raw_x[mask], raw_y[mask], raw_w[mask], n_total - int(mask.sum())


def pd_to_numeric(values) -> np.ndarray:
    """Coerce anything array-like to a float vector (bad values become NaN)."""
    import pandas as pd

    return pd.to_numeric(
        pd.Series(np.asarray(values, dtype=object).reshape(-1)), errors="coerce"
    ).to_numpy(dtype=float)


def _metrics(y: np.ndarray, fitted: np.ndarray, residuals: np.ndarray, n_params: int,
             weights: np.ndarray | None = None) -> dict:
    n = int(y.size)
    dof = n - n_params
    w = np.ones(n, dtype=float) if weights is None else weights
    chi2 = float(np.sum(w * residuals**2))
    ss_res = chi2
    ss_tot = float(np.sum(w * (y - np.average(y, weights=w)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    result = {
        "n_observations": n,
        "n_parameters": n_params,
        "degrees_of_freedom": dof,
        "r2": r2 if math.isfinite(r2) else None,
        "rmse": math.sqrt(float(np.mean(residuals**2))),
        "mae": float(np.mean(np.abs(residuals))),
        "max_abs_residual": float(np.max(np.abs(residuals))) if n else None,
        "chi2": chi2,
        "sse": float(np.sum(residuals**2)),
    }
    if dof > 0:
        sigma2 = chi2 / dof
        result["reduced_chi2"] = sigma2
        result["aic"] = float(n * math.log(max(ss_res / n, 1e-300)) + 2 * n_params)
        if ss_tot > 0:
            result["adjusted_r2"] = 1.0 - (1.0 - r2) * (n - 1) / dof
        else:
            result["adjusted_r2"] = None
        result["standard_error_regression"] = math.sqrt(max(sigma2, 0.0))
    else:
        result["reduced_chi2"] = None
        result["adjusted_r2"] = None
        result["aic"] = None
        result["standard_error_regression"] = None
        result["dof_warning"] = "No residual degrees of freedom; fit is underdetermined."
    if not math.isfinite(r2):
        result["r2_warning"] = "R² is undefined because the response is constant."
    return result


def _failure(model: str, reason: str, *, n_observations: int = 0,
             n_excluded: int = 0, warnings: list[str] | None = None) -> FitResult:
    spec = MODEL_SPECS.get(model, {})
    return FitResult(
        model=model,
        label=spec.get("label", model),
        success=False,
        assumptions=spec.get("assumptions", ""),
        reason=reason,
        n_observations=n_observations,
        n_excluded=n_excluded,
        warnings=list(warnings or []),
    )


def fit_linear(x, y, weights=None, *, x_label="x", y_label="y") -> FitResult:
    x_fit, y_fit, w, n_excluded = _prepare_pairs(x, y, weights)
    n = x_fit.size
    if n < 2:
        return _failure(MODEL_LINEAR, "At least two complete finite (X, Y, weight) pairs are required.",
                        n_observations=n, n_excluded=n_excluded)
    if np.ptp(x_fit) == 0:
        return _failure(MODEL_LINEAR, "X is constant; a slope cannot be identified.",
                        n_observations=n, n_excluded=n_excluded)

    # Weighted least squares in centred coordinates (avoids catastrophic
    # cancellation for large X offsets, e.g. timestamps near 1e9).
    sw = float(np.sum(w))
    x_bar = float(np.average(x_fit, weights=w))
    y_bar = float(np.average(y_fit, weights=w))
    dx = x_fit - x_bar
    sxx = float(np.sum(w * dx**2))
    sxy = float(np.sum(w * dx * (y_fit - y_bar)))
    if not np.isfinite(sxx) or sxx <= 0:
        return _failure(MODEL_LINEAR, "Weighted X variance is not positive and finite.",
                        n_observations=n, n_excluded=n_excluded)
    slope = sxy / sxx
    intercept = y_bar - slope * x_bar
    fitted = slope * x_fit + intercept
    residuals = y_fit - fitted
    metrics = _metrics(y_fit, fitted, residuals, 2, w)

    sigma2 = metrics.get("reduced_chi2")
    parameter_errors = {}
    if isinstance(sigma2, (int, float)) and math.isfinite(sigma2):
        parameter_errors["slope"] = math.sqrt(max(sigma2 / sxx, 0.0))
        parameter_errors["intercept"] = math.sqrt(max(sigma2 * (1.0 / sw + x_bar**2 / sxx), 0.0))
    else:
        # Absolute (not scaled) covariance from residual scatter.
        parameter_errors["slope"] = math.sqrt(max(float(np.sum(residuals**2)) / max(n - 2, 1) / sxx, 0.0))

    warnings = []
    if n == 2:
        warnings.append("Exactly two points: the line is interpolating, not estimating.")
    if weights is not None:
        warnings.append("Weights are treated as inverse variance (w = 1/sigma²); verify your uncertainty column.")
    return FitResult(
        model=MODEL_LINEAR,
        label=MODEL_SPECS[MODEL_LINEAR]["label"],
        success=True,
        parameters={"slope": float(slope), "intercept": float(intercept)},
        parameter_errors=parameter_errors,
        equation=f"{y_label} = {format_si(slope)} * {x_label} + {format_si(intercept)}",
        metrics=metrics,
        assumptions=MODEL_SPECS[MODEL_LINEAR]["assumptions"],
        warnings=warnings,
        residuals=residuals,
        x_fit=x_fit,
        n_observations=n,
        n_excluded=n_excluded,
        weighted=weights is not None,
        x_range=(float(np.min(x_fit)), float(np.max(x_fit))),
    )


def fit_polynomial(x, y, degree: int = 2, weights=None, *, x_label="x", y_label="y") -> FitResult:
    x_fit, y_fit, w, n_excluded = _prepare_pairs(x, y, weights)
    n = x_fit.size
    degree = int(degree)
    if degree < 1 or degree > 6:
        return _failure(MODEL_POLYNOMIAL, "Polynomial degree must be between 1 and 6.",
                        n_observations=n, n_excluded=n_excluded)
    if n < degree + 2:
        return _failure(MODEL_POLYNOMIAL,
                        f"A degree-{degree} polynomial needs at least {degree + 2} observations "
                        "to leave a residual degree of freedom.",
                        n_observations=n, n_excluded=n_excluded)
    if np.ptp(x_fit) == 0:
        return _failure(MODEL_POLYNOMIAL, "X is constant; polynomial terms are collinear.",
                        n_observations=n, n_excluded=n_excluded)

    offset = float(np.mean(x_fit))
    scale = float(np.ptp(x_fit)) or 1.0
    scaled_x = (x_fit - offset) / scale
    # Build Vandermonde from monomials (highest first) to match numpy.polynomial.
    design = np.vander(scaled_x, degree + 1, increasing=True)
    sqrt_w = np.sqrt(w)
    try:
        scaled_coeffs, *_ = np.linalg.lstsq(design * sqrt_w[:, None], y_fit * sqrt_w, rcond=None)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - guarded by checks above
        return _failure(MODEL_POLYNOMIAL, f"Matrix solve failed: {exc}",
                        n_observations=n, n_excluded=n_excluded)
    if not np.all(np.isfinite(scaled_coeffs)):
        return _failure(MODEL_POLYNOMIAL, "The polynomial fit produced non-finite coefficients.",
                        n_observations=n, n_excluded=n_excluded)
    # Compose the fitted polynomial in z=(x-offset)/scale with the linear
    # transform itself, giving coefficients in the ORIGINAL x units.
    transform = Polynomial([-offset / scale, 1.0 / scale])
    coefficients = np.asarray(Polynomial(scaled_coeffs)(transform).coef, dtype=float)

    fitted = np.polynomial.polynomial.polyval(x_fit, coefficients)
    if not np.all(np.isfinite(fitted)):
        return _failure(MODEL_POLYNOMIAL, "Predictions overflowed for this X range; try a lower degree.",
                        n_observations=n, n_excluded=n_excluded)
    residuals = y_fit - fitted
    metrics = _metrics(y_fit, fitted, residuals, degree + 1, w)
    equation = f"{y_label} = " + " + ".join(
        f"({format_si(value)})*{x_label}^{i}" if i else format_si(value)
        for i, value in enumerate(coefficients)
    )
    warnings = []
    if degree >= 3:
        warnings.append("Higher-degree polynomials are unstable outside the fitted X range.")
    if metrics.get("r2") is not None and metrics["r2"] > 0.999:
        warnings.append("An almost exact fit can indicate overfitting rather than a physical law.")
    return FitResult(
        model=MODEL_POLYNOMIAL,
        label=MODEL_SPECS[MODEL_POLYNOMIAL]["label"],
        success=True,
        parameters={f"c{i}": float(value) for i, value in enumerate(coefficients)},
        equation=equation,
        metrics=metrics,
        assumptions=MODEL_SPECS[MODEL_POLYNOMIAL]["assumptions"],
        warnings=warnings,
        residuals=residuals,
        x_fit=x_fit,
        n_observations=n,
        n_excluded=n_excluded,
        weighted=weights is not None,
        x_range=(float(np.min(x_fit)), float(np.max(x_fit))),
    )


def _exp_model(x, amplitude, rate, offset):
    with np.errstate(over="ignore", invalid="ignore"):
        return amplitude * np.exp(np.clip(rate * x, -700, 700)) + offset


def _log_model(x, amplitude, offset):
    return amplitude * np.log(x) + offset


def _power_model(x, amplitude, exponent):
    return amplitude * np.power(x, exponent)


_NONLINEAR = {
    MODEL_EXPONENTIAL: (_exp_model, ["amplitude", "rate", "offset"]),
    MODEL_LOGARITHMIC: (_log_model, ["amplitude", "offset"]),
    MODEL_POWER: (_power_model, ["amplitude", "exponent"]),
}


def _initial_guess(model: str, x: np.ndarray, y: np.ndarray) -> list[float]:
    span = float(np.ptp(x)) or 1.0
    y_span = float(np.ptp(y)) or 1.0
    if model == MODEL_EXPONENTIAL:
        rate = np.sign(np.corrcoef(x, y)[0, 1]) * 1.0 / span if np.ptp(y) else 0.1 / span
        return [max(y_span, 1e-6), float(rate or 0.1 / span), float(np.min(y))]
    if model == MODEL_LOGARITHMIC:
        return [float(y_span), float(np.min(y))]
    return [max(float(np.median(y)), 1e-6), 1.0]


def fit_nonlinear(model: str, x, y, weights=None, *, x_label="x", y_label="y",
                  maxfev: int = 20000) -> FitResult:
    if model not in _NONLINEAR:
        return _failure(model, f"Unknown nonlinear model: {model}.")
    x_fit, y_fit, w, n_excluded = _prepare_pairs(x, y, weights)
    n = x_fit.size
    func, names = _NONLINEAR[model]
    n_params = len(names)
    if n < n_params + 1:
        return _failure(model,
                        f"At least {n_params + 1} complete finite pairs are required for {model}.",
                        n_observations=n, n_excluded=n_excluded)
    if model in (MODEL_LOGARITHMIC, MODEL_POWER) and np.any(x_fit <= 0):
        return _failure(model,
                        f"{model} requires all fitted X values to be strictly positive; "
                        f"{int((x_fit <= 0).sum())} value(s) were not.",
                        n_observations=n, n_excluded=n_excluded)
    if model == MODEL_POWER and np.any(y_fit <= 0):
        return _failure(model,
                        "A power law y = A*x^k requires all fitted Y values to be strictly positive.",
                        n_observations=n, n_excluded=n_excluded)
    if np.ptp(x_fit) == 0 or np.ptp(y_fit) == 0:
        return _failure(model, "X and Y must both vary to fit this model.",
                        n_observations=n, n_excluded=n_excluded)

    p0 = _initial_guess(model, x_fit, y_fit)
    # curve_fit's sigma is a standard deviation, so sigma = 1/sqrt(w).
    sigma = 1.0 / np.sqrt(w) if weights is not None else None
    try:
        with np.errstate(all="ignore"):
            params, covariance = curve_fit(
                func, x_fit, y_fit, p0=p0, sigma=sigma,
                absolute_sigma=weights is not None, maxfev=maxfev,
            )
            fitted = func(x_fit, *params)
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError, OverflowError) as exc:
        return _failure(model,
                        f"Nonlinear optimisation did not converge: {type(exc).__name__}. "
                        "Try a different model, rescale the X column, or check for outliers.",
                        n_observations=n, n_excluded=n_excluded)
    if not np.all(np.isfinite(params)) or not np.all(np.isfinite(fitted)):
        return _failure(model, "The optimiser returned non-finite parameters or predictions.",
                        n_observations=n, n_excluded=n_excluded)
    residuals = y_fit - fitted
    metrics = _metrics(y_fit, fitted, residuals, n_params, w)
    errors = {}
    if np.all(np.isfinite(covariance)):
        errors = {name: float(math.sqrt(max(covariance[i, i], 0.0)))
                  for i, name in enumerate(names)}

    if model == MODEL_EXPONENTIAL:
        equation = (f"{y_label} = {format_si(params[0])} * "
                    f"exp({format_si(params[1])}*{x_label}) + {format_si(params[2])}")
    elif model == MODEL_LOGARITHMIC:
        equation = f"{y_label} = {format_si(params[0])} * ln({x_label}) + {format_si(params[1])}"
    else:
        equation = f"{y_label} = {format_si(params[0])} * {x_label}^({format_si(params[1])})"
    warnings = ["Nonlinear fits are sensitive to initial guesses; inspect residuals before trusting parameters."]
    if weights is not None:
        warnings.append("Weights are interpreted as inverse variance (w = 1/sigma²).")
    return FitResult(
        model=model,
        label=MODEL_SPECS[model]["label"],
        success=True,
        parameters={name: float(value) for name, value in zip(names, params, strict=True)},
        parameter_errors=errors,
        equation=equation,
        metrics=metrics,
        assumptions=MODEL_SPECS[model]["assumptions"],
        warnings=warnings,
        residuals=residuals,
        x_fit=x_fit,
        n_observations=n,
        n_excluded=n_excluded,
        weighted=weights is not None,
        x_range=(float(np.min(x_fit)), float(np.max(x_fit))),
    )


def fit_model(model: str, x, y, weights=None, *, degree: int = 2,
              x_label="x", y_label="y") -> FitResult:
    """Dispatch to the requested model. Unknown models fail gracefully."""
    if model == MODEL_LINEAR:
        return fit_linear(x, y, weights, x_label=x_label, y_label=y_label)
    if model == MODEL_POLYNOMIAL:
        return fit_polynomial(x, y, degree, weights, x_label=x_label, y_label=y_label)
    if model in _NONLINEAR:
        return fit_nonlinear(model, x, y, weights, x_label=x_label, y_label=y_label)
    return _failure(model, f"Unknown model '{model}'. Choose one of: "
                    + ", ".join(MODEL_SPECS) + ".")


def suggest_models(x, y) -> list[dict]:
    """Rank *candidate* models without claiming any is the true law."""
    px, py = pd_to_numeric(x), pd_to_numeric(y)
    mask = np.isfinite(px) & np.isfinite(py)
    a, b = px[mask], py[mask]
    suggestions = []
    caveat = ("Suggestions are shape heuristics based on linearised correlations. "
              "They are not model selection or proof of causation; compare residuals "
              "and AIC on the same data before choosing.")
    if a.size < 4:
        return [{"model": MODEL_LINEAR, "confidence": "low", "caveat": caveat,
                 "reason": "Too few complete pairs to compare model shapes; choose a model manually."}]
    with np.errstate(all="ignore"):
        pearson = float(np.corrcoef(a, b)[0, 1]) if np.ptp(a) and np.ptp(b) else float("nan")
        log_corr = (float(np.corrcoef(np.log(a), b)[0, 1])
                    if np.all(a > 0) and np.ptp(b) else float("nan"))
        exp_corr = (float(np.corrcoef(a, np.log(b))[0, 1])
                    if np.all(b > 0) and np.ptp(a) else float("nan"))
        power_corr = (float(np.corrcoef(np.log(a), np.log(b))[0, 1])
                      if np.all(a > 0) and np.all(b > 0) else float("nan"))
    candidates = [
        (MODEL_LINEAR, pearson),
        (MODEL_LOGARITHMIC, log_corr),
        (MODEL_EXPONENTIAL, exp_corr),
        (MODEL_POWER, power_corr),
    ]
    ranked = sorted(
        ((model, abs(value) if math.isfinite(value) else -1.0) for model, value in candidates),
        key=lambda item: item[1], reverse=True,
    )
    for rank, (model, score) in enumerate(ranked):
        confidence = "low"
        if rank == 0 and score > 0.98:
            confidence = "moderate"
        elif score > 0.9:
            confidence = "low"
        suggestions.append({
            "model": model,
            "label": MODEL_SPECS[model]["label"],
            "confidence": confidence,
            "caveat": caveat,
            "linearised_abs_correlation": score if score >= 0 else None,
            "reason": "Ranked by absolute correlation after model-specific linearisation only.",
        })
    suggestions.append({
        "model": MODEL_POLYNOMIAL,
        "label": MODEL_SPECS[MODEL_POLYNOMIAL]["label"],
        "confidence": "low",
        "caveat": caveat,
        "linearised_abs_correlation": None,
        "reason": "A polynomial can flexibly describe curvature but is not evidence of a mechanism.",
    })
    return suggestions


def predict_with_flags(result: FitResult, x_new) -> dict:
    """Predict with explicit in-range / extrapolation flags."""
    if not result.success:
        return {"valid": False, "reason": result.reason or "The model did not fit."}
    params = result.parameters
    values = pd_to_numeric(x_new)

    if result.model == MODEL_LINEAR:
        prediction = params["slope"] * values + params["intercept"]
    elif result.model == MODEL_POLYNOMIAL:
        prediction = np.polynomial.polynomial.polyval(
            values, np.array([params[key] for key in sorted(params)], dtype=float)
        )
    elif result.model == MODEL_EXPONENTIAL:
        prediction = _exp_model(values, params["amplitude"], params["rate"], params["offset"])
    elif result.model == MODEL_LOGARITHMIC:
        prediction = _log_model(values, params["amplitude"], params["offset"])
    elif result.model == MODEL_POWER:
        prediction = _power_model(values, params["amplitude"], params["exponent"])
    else:
        return {"valid": False, "reason": f"Prediction is not implemented for {result.model}."}

    finite = np.isfinite(prediction)
    low, high = result.x_range or (float("-inf"), float("inf"))
    flags = np.where(finite, np.where((values < low) | (values > high), "extrapolated", "in_range"), "undefined")
    return {
        "valid": True,
        "x": values.tolist(),
        "predicted": np.where(finite, prediction, np.nan).tolist(),
        "range_flags": flags.tolist(),
        "fitted_x_range": [low, high],
        "caveat": "Extrapolated values are model-based projections, not measured results.",
    }


def compare_models(results: list[FitResult]) -> list[dict]:
    """Rank successful fits by AIC (when available), then adjusted R²."""
    rows = []
    for result in results:
        if not result.success:
            rows.append({"model": result.model, "success": False, "reason": result.reason})
            continue
        rows.append({
            "model": result.model,
            "label": result.label,
            "success": True,
            "n_observations": result.n_observations,
            "n_parameters": result.metrics.get("n_parameters"),
            "r2": result.metrics.get("r2"),
            "adjusted_r2": result.metrics.get("adjusted_r2"),
            "rmse": result.metrics.get("rmse"),
            "aic": result.metrics.get("aic"),
            "warnings": result.warnings,
        })
    def key(row):
        if not row.get("success"):
            return (2, 0.0)
        aic = row.get("aic")
        if aic is None:
            return (1, -(row.get("adjusted_r2") or -1e9))
        return (0, -aic)
    return sorted(rows, key=key)
