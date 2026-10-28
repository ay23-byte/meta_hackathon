"""Independent synthetic checks for numerical correctness and overflow safety.

These tests use known-answer datasets; they do not claim universal scientific
validity. Floating-point comparisons use tolerances.
"""

from __future__ import annotations

import json
import math
import warnings

import numpy as np
import pandas as pd
import pytest

from analysis_core import analyze_linear
from data_io import coerce_numeric
from fitting_core import fit_linear, fit_model
from result_schema import json_safe
from statistics_core import describe_numeric

SLOPE = 2.5
INTERCEPT = 0.1


def synthetic_line(n: int = 12) -> tuple[np.ndarray, np.ndarray]:
    x = np.arange(n, dtype=float)
    y = SLOPE * x + INTERCEPT
    return x, y


def test_known_synthetic_line_is_recovered_by_both_engines():
    x, y = synthetic_line()
    general = fit_linear(x, y)
    legacy = analyze_linear(x, y)

    assert general.success
    assert general.parameters["slope"] == pytest.approx(SLOPE, rel=1e-12)
    assert general.parameters["intercept"] == pytest.approx(INTERCEPT, rel=1e-12)
    assert general.metrics["r2"] == pytest.approx(1.0, abs=1e-12)
    assert general.metrics["rmse"] == pytest.approx(0.0, abs=1e-12)
    assert legacy["slope"] == pytest.approx(SLOPE, rel=1e-12)
    assert legacy["intercept"] == pytest.approx(INTERCEPT, rel=1e-12)
    assert legacy["r_squared"] == pytest.approx(1.0, abs=1e-12)
    assert np.asarray(legacy["fitted"]) + np.asarray(legacy["residuals"]) == pytest.approx(y)


def test_residuals_and_json_serialization_stay_finite():
    x, y = synthetic_line()
    fit = fit_linear(x, y)
    assert np.all(np.isfinite(fit.residuals))
    payload = json.dumps(json_safe(fit.as_dict()), allow_nan=False)
    assert "NaN" not in payload and "Infinity" not in payload


def test_extremely_large_but_finite_values_are_not_reported_as_nan_success():
    """Regression: 1e308 responses used to yield success=True with NaN slope."""
    x = np.arange(4, dtype=float)
    y = np.array([1e308, 1.1e308, 1.2e308, 1.3e308])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        fit = fit_linear(x, y)
        dispatched = fit_model("linear", x, y)
        stats = describe_numeric(y)

    assert fit.success is False and "non-finite" in fit.reason.casefold()
    assert dispatched.success is False
    assert stats["valid"] is False
    assert "Non-finite summary" in stats["reason"]
    assert stats["mean"] is None and stats["std_sample"] is None
    assert stats["ci_mean_95"] is None
    assert math.isfinite(stats["min"]) and math.isfinite(stats["max"])
    with pytest.raises(ValueError, match="too large"):
        analyze_linear(x, y)


def test_zero_variance_and_insufficient_samples_have_explicit_outcomes():
    assert fit_linear([1, 1, 1], [1, 2, 3]).success is False
    assert "constant" in fit_linear([1, 1, 1], [1, 2, 3]).reason.casefold()
    assert fit_linear([1], [2]).success is False
    assert analyze_linear([0, 1, 2, 3], [5, 5, 5, 5])["r_squared"] is None
    with pytest.raises(ValueError, match="At least two"):
        analyze_linear([0], [1])


def test_nonfinite_pairs_are_excluded_never_zero_filled():
    x = ["0", "1", "2", "3", "4"]
    y = ["0.1", "2.6", "NaN", "inf", "oops"]
    fit = fit_linear(x, y)
    assert fit.success is False or fit.n_observations == 2
    coercion = coerce_numeric(pd.Series(y))
    assert coercion.n_valid == 2
    assert int(coercion.missing.sum()) == 1
    assert int(coercion.nonfinite.sum()) == 1
    assert int(coercion.invalid.sum()) == 1
    assert 0.0 not in coercion.values[np.isfinite(coercion.values)]


def test_nonpositive_weights_are_not_silently_accepted():
    x, y = synthetic_line(6)
    fit = fit_linear(x, y, weights=np.zeros_like(x))
    assert fit.success is False
    assert "At least two" in fit.reason or "variance" in fit.reason.casefold()


def test_fixed_seed_reproduces_the_same_synthetic_dataset_and_fit():
    rng = np.random.default_rng(20261027)
    x = np.linspace(0, 5, 20)
    y = 1.7 * x - 0.4 + rng.normal(0, 0.1, size=x.size)
    fit = fit_linear(x, y)
    rng2 = np.random.default_rng(20261027)
    y2 = 1.7 * x - 0.4 + rng2.normal(0, 0.1, size=x.size)
    fit2 = fit_linear(x, y2)
    assert fit.parameters["slope"] == pytest.approx(fit2.parameters["slope"], rel=1e-12)
    assert fit.parameters["intercept"] == pytest.approx(fit2.parameters["intercept"], rel=1e-12)
