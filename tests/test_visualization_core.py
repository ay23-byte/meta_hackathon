"""Charts work with arbitrary headers and never invent uncertainties."""

import numpy as np
import pandas as pd
import pytest

from fitting_core import fit_linear
from visualization_core import PLOT_TYPES, build_chart, render_png


@pytest.fixture
def frame():
    rng = np.random.default_rng(11)
    n = 30
    x = np.linspace(1, 10, n)
    return pd.DataFrame({
        "temperature °C": x,
        "signal (a.u.)": 2 * x + rng.normal(0, 0.4, n),
        "err sigma": np.full(n, 0.25),
        "batch": ["A", "B"] * (n // 2),
        "date": pd.date_range("2026-02-01", periods=n, freq="D"),
    })


@pytest.fixture
def config(frame):
    return {
        "x": "temperature °C", "y": "signal (a.u.)", "group": "batch",
        "time": "date", "uncertainty": "err sigma", "secondary_y": [],
        "bins": 20,
        "numeric_columns": ["temperature °C", "signal (a.u.)", "err sigma"],
        "fit_result": fit_linear(frame["temperature °C"], frame["signal (a.u.)"]),
    }


def test_every_plot_type_builds_html_and_png(frame, config):
    for plot_type in PLOT_TYPES:
        spec = build_chart(plot_type, frame, config)
        assert spec.valid, f"{plot_type}: {spec.reason}"
        assert spec.n_rows > 0
        html = spec.to_html()
        assert "vega" in html.lower()
        assert spec.label in html
        assert render_png(plot_type, frame, config).startswith(b"\x89PNG")


def test_arbitrary_headers_with_spaces_units_and_punctuation(frame, config):
    spec = build_chart("scatter", frame, config)
    assert spec.valid
    assert "temperature °C" in spec.to_html()


def test_error_bars_require_an_uncertainty_column(frame, config):
    without = dict(config, uncertainty=None)
    spec = build_chart("errorbar", frame, without)
    assert not spec.valid
    assert "will not invent" in spec.reason
    assert render_png("errorbar", frame, without).startswith(b"\x89PNG")


def test_secondary_y_does_not_create_a_misleading_dual_axis(frame, config):
    spec = build_chart("scatter", frame, dict(config, secondary_y=["signal (a.u.)"]))
    assert any("dual axes" in warning for warning in spec.warnings)


def test_residual_plot_requires_a_successful_fit(frame, config):
    spec = build_chart("residuals", frame, dict(config, fit_result=None))
    assert not spec.valid
    assert "Fit a model" in spec.reason


def test_heatmap_leaves_undefined_cells_blank():
    frame = pd.DataFrame({"a": [1, 2, 3], "b": [2, 4, 6], "flat": [5, 5, 5]})
    spec = build_chart("correlation_heatmap", frame,
                       {"numeric_columns": ["a", "b", "flat"], "x": "a", "y": "b"})
    assert spec.valid
    assert spec.n_rows < 9  # constant column contributes NaNs that were dropped


def test_unsorted_line_data_produces_a_warning():
    frame = pd.DataFrame({"x": [3, 1, 2, 5, 4], "y": [9, 1, 4, 25, 16]})
    spec = build_chart("line", frame, {"x": "x", "y": "y", "numeric_columns": ["x", "y"]})
    assert any("not sorted" in warning for warning in spec.warnings)


def test_grouped_comparison_warns_that_bars_are_means(frame, config):
    spec = build_chart("grouped_bar", frame, config)
    assert spec.valid
    assert any("arithmetic mean" in warning for warning in spec.warnings)


def test_unknown_plot_type_and_missing_columns_fail_cleanly(frame, config):
    spec = build_chart("rainbow", frame, config)
    assert not spec.valid and "Unknown plot type" in spec.reason
    spec = build_chart("scatter", frame, dict(config, y="does-not-exist"))
    assert not spec.valid and "Missing column" in spec.reason


def test_time_series_accepts_numeric_and_datetime_axes(frame, config):
    spec = build_chart("time_series", frame, config)
    assert spec.valid
    numeric = dict(config, time="temperature °C")
    assert build_chart("time_series", frame, numeric).valid
