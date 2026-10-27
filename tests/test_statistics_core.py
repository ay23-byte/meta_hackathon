"""Descriptive statistics with known synthetic values."""

import math

import numpy as np
import pandas as pd
import pytest

from statistics_core import (
    confidence_interval_mean,
    correlation,
    correlation_matrix,
    covariance,
    describe_numeric,
    descriptive_table,
    outlier_diagnostics,
)


def test_descriptive_statistics_on_known_values():
    summary = describe_numeric([1, 2, 3, 4, 5])
    assert summary["n_valid"] == 5
    assert summary["mean"] == pytest.approx(3.0)
    assert summary["median"] == pytest.approx(3.0)
    assert summary["min"] == 1 and summary["max"] == 5
    assert summary["q1"] == pytest.approx(2.0)
    assert summary["q3"] == pytest.approx(4.0)
    assert summary["variance_sample"] == pytest.approx(2.5)
    assert summary["std_sample"] == pytest.approx(math.sqrt(2.5))
    assert summary["variance_population"] == pytest.approx(2.0)
    assert summary["ci_mean_95"][0] < 3.0 < summary["ci_mean_95"][1]
    assert "Student-t" in summary["ci_mean_method"]


def test_missing_and_invalid_values_are_counted_without_zero_filling():
    summary = describe_numeric(["1", "", "oops", "inf", "3"])
    assert summary["n_total"] == 5
    assert summary["n_valid"] == 2
    assert summary["n_missing_or_invalid"] == 2
    assert summary["n_infinite"] == 1
    assert summary["mean"] == pytest.approx(2.0)


def test_insufficient_data_reports_instead_of_returning_nan():
    summary = describe_numeric([7])
    assert summary["valid"] is False
    assert summary["std_sample"] is None
    assert "At least two" in summary["reason"]
    assert describe_numeric([])["valid"] is False


def test_t_interval_is_symmetric_with_known_width():
    interval = confidence_interval_mean([1, 2, 3, 4, 5])["interval"]
    assert interval[0] == pytest.approx(3 - (interval[1] - 3))
    assert confidence_interval_mean([5, 5, 5])["interval"] == [5.0, 5.0]


def test_correlation_and_covariance_on_known_pairs():
    x = np.array([0, 1, 2, 3, 4], dtype=float)
    y = 2 * x + 1
    result = correlation(x, y)
    assert result["coefficient"] == pytest.approx(1.0)
    assert result["n_valid"] == 5
    assert 0 <= result["p_value"] <= 1
    assert "not causation" in result["caveat"]
    assert covariance(x, y)["value"] == pytest.approx(5.0)


def test_spearman_is_perfect_for_monotone_nonlinear_data():
    x = np.arange(1, 8, dtype=float)
    result = correlation(x, x**3, method="spearman")
    assert result["coefficient"] == pytest.approx(1.0)


def test_correlation_handles_constant_mismatched_and_sparse_pairs():
    assert correlation([1, 1, 1, 1], [1, 2, 3, 4])["valid"] is False
    assert "different lengths" in correlation([1, 2], [1, 2, 3])["reason"]
    assert correlation([1, 2, np.nan, 4], [1, 2, 3, 4])["n_valid"] == 3
    assert "Unsupported" in correlation([1, 2, 3], [1, 2, 3], method="kendall")["reason"]


def test_correlation_matrix_leaves_undefined_entries_nan():
    frame = pd.DataFrame({"a": [1, 2, 3], "b": [2, 4, 6], "c": [5, 5, 5]})
    matrix = correlation_matrix(frame, ["a", "b", "c"])
    assert matrix.loc["a", "b"] == pytest.approx(1.0)
    assert np.isnan(matrix.loc["a", "c"])
    assert matrix.loc["c", "c"] == 1.0


def test_outliers_are_flagged_but_never_removed():
    values = [10, 11, 10, 11, 10, 11, 100]
    result = outlier_diagnostics(values)
    assert result["n_high"] == 1
    assert result["n_valid"] == 7
    assert "NOT removed" in result["caveat"]
    assert outlier_diagnostics([1, 2, 3])["valid"] is False


def test_descriptive_table_has_one_row_per_statistic():
    frame = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
    table = descriptive_table(frame, ["a", "b"])
    assert "ci95_low" in table["statistic"].tolist()
    assert "ci95_high" in table["statistic"].tolist()
    assert list(table.columns) == ["statistic", "a", "b"]
    assert table.loc[table["statistic"] == "mean", "a"].iloc[0] == pytest.approx(2.0)
