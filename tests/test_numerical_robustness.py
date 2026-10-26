"""Independent checks of the deterministic OLS contract."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis_core import (
    analyze_linear,
    prepare_analysis_data,
    propose_measurements,
    serialize_analysis_exports,
)

ROOT = Path(__file__).resolve().parents[1]


def test_fit_matches_independent_lstsq_oracle():
    rng = np.random.default_rng(20261026)
    x = np.linspace(-3, 7, 17)
    y = 2.5 * x - 4.0 + rng.normal(0, 0.4, size=x.size)

    result = analyze_linear(x, y)
    design = np.column_stack([x, np.ones_like(x)])
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]

    assert result["slope"] == pytest.approx(slope, rel=1e-12, abs=1e-12)
    assert result["intercept"] == pytest.approx(intercept, rel=1e-12, abs=1e-12)
    assert result["n"] == x.size
    assert np.asarray(result["fitted"]) == pytest.approx(design @ [slope, intercept])
    assert np.asarray(result["residuals"]) == pytest.approx(y - design @ [slope, intercept])


def test_large_offset_keeps_intercept_accurate():
    """np.polyfit on these inputs returns an intercept near -79, not 2.

    Centred normal equations keep the same OLS solution while avoiding the
    loss of precision in an uncentred Vandermonde matrix.
    """
    x = np.array([1e9, 1e9 + 1, 1e9 + 2, 1e9 + 3], dtype=float)
    y = 5.0 * x + 2.0

    result = analyze_linear(x, y)

    assert result["slope"] == pytest.approx(5.0, abs=1e-9)
    assert result["intercept"] == pytest.approx(2.0, abs=1e-5)
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["rmse"] == pytest.approx(0.0, abs=1e-9)


def test_fit_is_invariant_to_row_permutation():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 2.9, 4.8, 7.2, 8.9])
    order = [3, 0, 4, 1, 2]

    base = analyze_linear(x, y)
    shuffled = analyze_linear(x[order], y[order])

    for key in ("slope", "intercept", "r_squared", "rmse"):
        assert shuffled[key] == pytest.approx(base[key], rel=1e-12)


def test_affine_rescaling_transforms_coefficients_consistently():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = 3.0 * x + 1.0
    base = analyze_linear(x, y)

    x2 = 2.0 * x + 10.0
    y2 = 5.0 * y - 7.0
    scaled = analyze_linear(x2, y2)

    # x2 = 2x+10, y2 = 5y-7  =>  slope' = 5*slope/2, intercept' adjusts.
    assert scaled["slope"] == pytest.approx(5.0 * base["slope"] / 2.0)
    expected_intercept = 5.0 * (base["slope"] * (-5.0) + base["intercept"]) - 7.0
    assert scaled["intercept"] == pytest.approx(expected_intercept)
    assert scaled["r_squared"] == pytest.approx(base["r_squared"])


def test_r_squared_and_rmse_definitions():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([1.0, 2.0, 4.0, 4.0])
    result = analyze_linear(x, y)

    residuals = np.asarray(result["residuals"])
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))

    assert result["r_squared"] == pytest.approx(1.0 - ss_res / ss_tot)
    assert result["rmse"] == pytest.approx(np.sqrt(ss_res / y.size))
    assert np.asarray(result["fitted"]) + residuals == pytest.approx(y)


def test_negative_slope_is_supported():
    result = analyze_linear([0, 1, 2, 3], [10, 8, 6, 4])
    assert result["slope"] == pytest.approx(-2.0)
    assert result["intercept"] == pytest.approx(10.0)


@pytest.mark.parametrize(
    "current, voltage, message",
    [
        ([0, 1], [1], "equal lengths"),
        ([0], [1], "At least two"),
        ([0, 1, 2], [1, 2, np.nan], "finite"),
        ([0, np.inf, 2], [1, 2, 3], "finite"),
        ([2, 2, 2], [1, 2, 3], "vary"),
    ],
)
def test_invalid_inputs_are_rejected(current, voltage, message):
    with pytest.raises(ValueError, match=message):
        analyze_linear(current, voltage)


def test_constant_voltage_leaves_r_squared_undefined_not_zero():
    result = analyze_linear([0, 1, 2, 3], [5, 5, 5, 5])
    assert result["r_squared"] is None
    assert result["rmse"] == pytest.approx(0.0, abs=1e-12)


def test_non_default_dataframe_index_does_not_misalign_pairs():
    frame = pd.DataFrame(
        {"I": [0.0, 1.0, 2.0, 3.0], "V": [0.5, 2.5, 4.5, 6.5]}
    )
    frame.index = ["row_a", "row_b", "row_c", "row_d"]

    prepared = prepare_analysis_data(frame, "I", "V")

    assert prepared["valid_rows"] == 4
    assert prepared["data"]["source_row"].tolist() == [1, 2, 3, 4]
    assert prepared["current"] == pytest.approx([0.0, 1.0, 2.0, 3.0])
    assert prepared["voltage"] == pytest.approx([0.5, 2.5, 4.5, 6.5])


def test_missing_or_empty_inputs_are_rejected_explicitly():
    frame = pd.DataFrame({"I": [0.0, 1.0], "V": [1.0, 2.0]})

    with pytest.raises(ValueError, match="Selected column not found"):
        prepare_analysis_data(frame, "missing", "V")
    with pytest.raises(ValueError, match="no data rows"):
        prepare_analysis_data(frame.iloc[0:0], "I", "V")
    with pytest.raises(ValueError, match="Selected column not found"):
        prepare_analysis_data(pd.DataFrame(), "I", "V")


@pytest.mark.parametrize(
    "candidates, observed, message",
    [
        ([], [0, 1], "finite proposed current"),
        ([1, float("nan")], [0, 1], "finite proposed current"),
        ([1], [], "Observed current values"),
        ([1], [0, float("inf")], "Observed current values"),
    ],
)
def test_proposal_rejects_invalid_inputs(candidates, observed, message):
    analysis = analyze_linear([0, 1, 2], [1, 3, 5])
    with pytest.raises(ValueError, match=message):
        propose_measurements(candidates, analysis, observed)


def test_export_serializer_handles_all_numpy_scalar_types():
    record = {
        "array": np.array([1.0, 2.0]),
        "integer": np.int64(7),
        "flag": np.bool_(False),
        "floating": np.float64(2.5),
        "infinite": np.float64(np.inf),
        "nested": {"tuple": (1, 2), "text": "ok"},
    }
    exports = serialize_analysis_exports(
        record, pd.DataFrame({"x": [1]}), "# report"
    )
    decoded = json.loads(exports["json"])
    assert decoded["array"] == [1.0, 2.0]
    assert decoded["integer"] == 7 and isinstance(decoded["integer"], int)
    assert decoded["flag"] is False
    assert decoded["floating"] == 2.5
    assert decoded["infinite"] is None
    assert decoded["nested"]["tuple"] == [1, 2]


def test_extreme_magnitudes_fail_loudly_instead_of_returning_nonsense():
    x = np.array([1.5e200, -1.5e200, 1.5e200, -1.5e200])
    y = np.array([1.5e200, -1.5e200, 1.5e200, -1.5e200])
    with pytest.raises(ValueError):
        analyze_linear(x, y)


def test_sample_dataset_results_are_stable():
    """Guard the published demo numbers against accidental regressions."""
    frame = pd.read_csv(ROOT / "data" / "sample_voltage_current.csv")
    prepared = prepare_analysis_data(frame, "current_A", "voltage_V")
    result = analyze_linear(prepared["current"], prepared["voltage"])

    assert prepared["original_rows"] == 11
    assert prepared["valid_rows"] == 11
    assert result["slope"] == pytest.approx(4.9909090909, rel=1e-8)
    assert result["intercept"] == pytest.approx(0.00545454545, abs=1e-8)
    assert result["r_squared"] == pytest.approx(0.9998029592, rel=1e-8)
    assert result["rmse"] == pytest.approx(0.0221564684, rel=1e-8)
