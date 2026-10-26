
import numpy as np
import pandas as pd
import pytest

from analysis_core import (
    analyze_linear,
    detect_candidate_columns,
    prepare_analysis_data,
    propose_measurements,
    serialize_analysis_exports,
)


def test_linear_fit_recovers_exact_line():
    result = analyze_linear([0, 1, 2, 3], [1, 3, 5, 7])

    assert result["slope"] == pytest.approx(2.0)
    assert result["intercept"] == pytest.approx(1.0)
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["rmse"] == pytest.approx(0.0)


def test_column_detection():
    columns = ["Time", "Current (A)", "Voltage (V)"]

    assert detect_candidate_columns(columns, "current") == "Current (A)"
    assert detect_candidate_columns(columns, "voltage") == "Voltage (V)"


def test_ambiguous_column_detection_returns_none():
    columns = ["Current", "Current (A)"]

    assert detect_candidate_columns(columns, "current") is None


def test_invalid_measurement_type_raises():
    with pytest.raises(ValueError):
        detect_candidate_columns(["A"], "temperature")


def test_prepare_data_excludes_invalid_pairs():
    frame = pd.DataFrame({
        "I": [0, "bad", 2],
        "V": [1, 2, np.inf],
    })

    result = prepare_analysis_data(frame, "I", "V")

    assert result["original_rows"] == 3
    assert result["valid_rows"] == 1
    assert result["dropped_rows"] == 2
    assert result["data"]["source_row"].tolist() == [1]


def test_same_columns_are_rejected():
    frame = pd.DataFrame({"I": [1, 2]})

    with pytest.raises(ValueError):
        prepare_analysis_data(frame, "I", "I")


def test_constant_current_is_rejected():
    with pytest.raises(ValueError):
        analyze_linear([1, 1, 1], [2, 3, 4])


def test_constant_voltage_has_undefined_r_squared():
    result = analyze_linear([0, 1, 2], [4, 4, 4])

    assert result["r_squared"] is None


def test_duplicate_column_names_are_rejected():
    frame = pd.DataFrame(
        [[0.0, 0.1, 3.0], [1.0, 2.0, 4.0], [2.0, 3.0, 5.0]],
        columns=["current_A", "voltage_V", "current_A"],
    )

    with pytest.raises(ValueError, match="Duplicate column names"):
        prepare_analysis_data(frame, "current_A", "voltage_V")


def test_measurement_explorer_flags_extrapolation():
    analysis = analyze_linear([0, 1, 2], [1, 3, 5])
    result = propose_measurements([-1, 1, 3], analysis, [0, 1, 2])

    assert result["within_observed_range"].tolist() == [
        False, True, False
    ]


def test_export_converts_nan_to_json_null():
    result = serialize_analysis_exports(
        {"value": float("nan")},
        pd.DataFrame({"x": [1]}),
        "# Report",
    )

    assert '"value": null' in result["json"]
    assert "x" in result["csv"]
    assert result["markdown"] == "# Report"
