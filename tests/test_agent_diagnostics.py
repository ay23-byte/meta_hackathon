"""Deterministic diagnostics: thresholds, quality gate and retry selection."""

import numpy as np
import pytest

from agent_diagnostics import (
    FAILED,
    INSUFFICIENT,
    PASS,
    POOR_FIT,
    choose_alternative,
    classify_quality,
    diagnose_fit,
    residual_runs,
)
from fitting_core import fit_model


def test_residual_runs_detects_structure_and_randomness():
    rng = np.random.default_rng(3)
    random = rng.normal(0, 1, 60)
    alternating = np.array([1.0, -1.0] * 20)
    drift = np.linspace(-2.0, 2.0, 60)
    assert residual_runs(random)["structured"] is False
    assert residual_runs(alternating)["structured"] is True
    assert residual_runs(drift)["structured"] is True
    assert residual_runs(np.array([1.0, 2.0]))["reason"]
    assert residual_runs(np.full(30, 1e-15))["structured"] is False


def test_good_linear_fit_passes():
    x = np.linspace(0, 10, 30)
    fit = fit_model("linear", x, 2.5 * x + 1.0)
    result = diagnose_fit(fit, x, 2.5 * x + 1.0)
    assert result["verdict"] == PASS
    assert result["r2"] == pytest.approx(1.0)


def test_linear_fit_on_quadratic_data_is_poor():
    x = np.linspace(-4, 4, 25)
    y = 1.5 - 0.7 * x + 0.35 * x**2
    fit = fit_model("linear", x, y)
    result = diagnose_fit(fit, x, y)
    assert result["verdict"] == POOR_FIT
    assert any("R2" in reason for reason in result["reasons"])


def test_constant_response_is_insufficient():
    x = np.arange(6, dtype=float)
    fit = fit_model("linear", x, np.full(6, 5.0))
    result = diagnose_fit(fit, x, np.full(6, 5.0))
    assert result["verdict"] == INSUFFICIENT
    assert result["r2"] is None


def test_failed_fit_is_classified_without_exception():
    fit = fit_model("linear", [1, 1, 1], [1, 2, 3])
    result = diagnose_fit(fit)
    assert result["verdict"] == FAILED
    assert result["reasons"]


def test_quality_gate_continue_with_recovery():
    quality = {
        "rows": 9, "numeric_columns": ["x", "y"], "n_valid_pairs": 6,
        "duplicate_headers": [], "ambiguous_roles": False,
        "missing": 1, "invalid": 1, "nonfinite": 1,
        "invalid_ratio": {"x": 0.0, "y": 0.2},
        "suggested_x": "x", "suggested_y": "y",
    }
    gate = classify_quality(quality)
    assert gate["decision"] == "CONTINUE"
    assert gate["recovery"]
    assert "no observation was removed" not in " ".join(gate["recovery"])


@pytest.mark.parametrize("patch, expected", [
    ({"duplicate_headers": ["signal"]}, "NEEDS_CLARIFICATION"),
    ({"numeric_columns": ["x"]}, "NEEDS_CLARIFICATION"),
    ({"invalid_ratio": {"x": 0.0, "y": 0.9}}, "NEEDS_CLARIFICATION"),
    ({"n_valid_pairs": 2}, "INSUFFICIENT_EVIDENCE"),
])
def test_quality_gate_halts_on_clarification_or_insufficient(patch, expected):
    quality = {
        "rows": 9, "numeric_columns": ["x", "y"], "n_valid_pairs": 6,
        "duplicate_headers": [], "ambiguous_roles": False,
        "missing": 0, "invalid": 0, "nonfinite": 0,
        "invalid_ratio": {"x": 0.0, "y": 0.0},
        "suggested_x": "x", "suggested_y": "y",
    }
    quality.update(patch)
    assert classify_quality(quality)["decision"] == expected


def test_choose_alternative_respects_budget_and_skips_tried_models():
    assert choose_alternative(["linear"], ["polynomial", "exponential"], 3) == "polynomial"
    assert choose_alternative(["linear", "polynomial"], ["polynomial", "exponential"], 3) == "exponential"
    assert choose_alternative(["linear", "polynomial", "exponential"],
                              ["polynomial", "exponential"], 3) is None
