"""Fitting engine: exact recovery, weighting, failures and extrapolation."""

import math

import numpy as np
import pytest

from fitting_core import (
    MODEL_SPECS,
    compare_models,
    fit_linear,
    fit_model,
    fit_polynomial,
    predict_with_flags,
    suggest_models,
)


def test_linear_fit_recovers_known_parameters_even_with_large_x_offset():
    x = 1e9 + np.arange(7, dtype=float)
    y = 3.25 * x - 17.0
    fit = fit_linear(x, y)
    assert fit.success
    assert fit.parameters["slope"] == pytest.approx(3.25, rel=1e-10)
    assert fit.parameters["intercept"] == pytest.approx(-17.0, rel=1e-6, abs=1e-4)
    assert fit.metrics["r2"] == pytest.approx(1.0)


def test_weighted_linear_fit_uses_inverse_variance_weights():
    x = np.array([0, 1, 2, 3, 4, 5], dtype=float)
    y = np.array([1.0, 3.1, 4.9, 7.2, 8.8, 100.0])  # last point is an outlier
    sigma = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 100.0])
    unweighted = fit_linear(x, y)
    weighted = fit_linear(x, y, weights=1 / sigma**2)
    assert weighted.weighted
    assert abs(weighted.parameters["slope"] - 2.0) < abs(unweighted.parameters["slope"] - 2.0)


def test_polynomial_fit_returns_coefficients_in_original_units():
    x = np.linspace(-3, 5, 30)
    y = 1.5 - 0.7 * x + 0.35 * x**2
    fit = fit_polynomial(x, y, degree=2)
    assert fit.success
    assert fit.parameters["c0"] == pytest.approx(1.5, abs=1e-8)
    assert fit.parameters["c1"] == pytest.approx(-0.7, abs=1e-8)
    assert fit.parameters["c2"] == pytest.approx(0.35, abs=1e-8)
    assert fit.metrics["r2"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "model,function,expected",
    [
        ("exponential", lambda x: 2.0 * np.exp(0.4 * x) + 3.0, {"amplitude": 2.0, "rate": 0.4, "offset": 3.0}),
        ("logarithmic", lambda x: 3.0 * np.log(x) + 1.0, {"amplitude": 3.0, "offset": 1.0}),
        ("power", lambda x: 2.0 * x**1.5, {"amplitude": 2.0, "exponent": 1.5}),
    ],
)
def test_nonlinear_models_recover_known_parameters(model, function, expected):
    x = np.linspace(1, 6, 25)
    fit = fit_model(model, x, function(x))
    assert fit.success, fit.reason
    for name, value in expected.items():
        assert fit.parameters[name] == pytest.approx(value, rel=1e-5)


def test_model_assumptions_are_reported_for_every_choice():
    assert all(spec["assumptions"] for spec in MODEL_SPECS.values())
    x = np.arange(1, 10, dtype=float)
    for model in MODEL_SPECS:
        fit = fit_model(model, x, 2 * x + 1)
        assert fit.assumptions == MODEL_SPECS[model]["assumptions"]


def test_failures_are_structured_not_exceptions():
    assert not fit_linear([1, 2], [1, np.nan]).success
    assert "constant" in fit_linear([1, 1, 1], [1, 2, 3]).reason
    assert "degree" in fit_polynomial([1, 2], [1, 2], degree=9).reason
    assert "positive" in fit_model("logarithmic", [-1, 0, 1], [1, 2, 3]).reason
    assert "Unknown model" in fit_model("magic", [1, 2], [1, 2]).reason
    assert "At least" in fit_model("exponential", [1, 2], [1, 2]).reason


def test_predictions_flag_extrapolation():
    x = np.arange(0, 6, dtype=float)
    fit = fit_linear(x, 2 * x + 1)
    prediction = predict_with_flags(fit, [2, 3, 20])
    assert prediction["range_flags"] == ["in_range", "in_range", "extrapolated"]
    assert prediction["predicted"][2] == pytest.approx(41.0)
    assert "not measured" in prediction["caveat"]


def test_prediction_works_for_every_model_family():
    x = np.linspace(1, 5, 20)
    for model in ("linear", "polynomial", "exponential", "logarithmic", "power"):
        fit = fit_model(model, x, 2 * x + 1)
        if fit.success:
            result = predict_with_flags(fit, [2.0, 3.0])
            assert result["valid"] and len(result["predicted"]) == 2


def test_model_suggestions_are_labelled_as_heuristics():
    x = np.linspace(1, 5, 20)
    suggestions = suggest_models(x, 2 * np.exp(0.3 * x))
    assert all("caveat" in item for item in suggestions)
    assert all(item["confidence"] in ("low", "moderate") for item in suggestions)
    assert all("model" in item for item in suggestions)
    assert len(suggestions) == 5


def test_model_comparison_orders_by_aic_and_reports_failures():
    x = np.linspace(1, 5, 20)
    y = 2 * x + 1
    good = fit_linear(x, y)
    bad = fit_model("power", x, y)
    rows = compare_models([bad, good])
    assert rows[0]["model"] == "linear" or rows[0]["aic"] is not None
    assert any(row["model"] == "power" for row in rows)
    assert all(math.isfinite(row["r2"]) for row in rows if row["success"] and row["r2"] is not None)


def test_weighted_linear_parameter_errors_use_absolute_input_uncertainties():
    # An exact line must not erase the supplied measurement uncertainty.
    x = np.array([0., 1., 2., 3.])
    sigma = np.array([0.2, 0.4, 0.3, 0.5])
    design = np.column_stack((np.ones_like(x), x))
    covariance = np.linalg.inv(design.T @ np.diag(1 / sigma**2) @ design)
    fit = fit_linear(x, 1 + 2 * x, weights=1 / sigma**2)
    assert fit.success
    assert fit.parameter_errors["intercept"] == pytest.approx(np.sqrt(covariance[0, 0]))
    assert fit.parameter_errors["slope"] == pytest.approx(np.sqrt(covariance[1, 1]))
    assert "absolute inverse variances" in " ".join(fit.warnings)


def test_two_point_linear_fit_does_not_invent_residual_based_errors():
    fit = fit_linear([0, 1], [1, 3])
    assert fit.success
    assert fit.parameter_errors == {}
    assert "unavailable" in " ".join(fit.warnings)
    # With known, supplied measurement variances, covariance is still defined,
    # but the two-point data cannot assess residual scatter or goodness of fit.
    weighted = fit_linear([0, 1], [1, 3], weights=[100, 100])
    assert weighted.parameter_errors["slope"] == pytest.approx(np.sqrt(0.02))
    assert weighted.parameter_errors["intercept"] == pytest.approx(0.1)
    assert weighted.metrics["degrees_of_freedom"] == 0


def test_exponential_overflow_is_undefined_not_silently_clipped():
    x = np.linspace(1, 6, 25)
    fit = fit_model("exponential", x, 2 * np.exp(.4 * x) + 3)
    assert fit.success
    result = predict_with_flags(fit, [2000.0])
    assert result["range_flags"] == ["undefined"]
    assert math.isnan(result["predicted"][0])


def test_tiny_imperfect_fit_refuses_underflowed_diagnostics():
    fit = fit_linear([0, 1, 2, 3], [1e-200, 2e-200, 3e-200, 5e-200])
    assert not fit.success
    assert "underflow" in fit.reason
    assert fit.parameter_errors == {}


def test_large_x_offset_does_not_overflow_intercept_error_calculation():
    x = np.array([1e155, 1.00001e155, 1.00002e155])
    fit = fit_linear(x, [1, 2, 3])
    assert fit.success, fit.reason
    assert math.isfinite(fit.parameter_errors["intercept"])


@pytest.mark.parametrize("sigma", [[1e-200], [1e200], [0], [float("inf")]])
def test_inverse_variance_weights_reject_unrepresentable_inputs(sigma):
    from fitting_core import inverse_variance_weights

    with pytest.raises(ValueError):
        inverse_variance_weights(sigma)


def test_inverse_variance_weights_preserve_known_values():
    from fitting_core import inverse_variance_weights

    assert inverse_variance_weights([0.5, 2.0]) == pytest.approx([4.0, 0.25])
