"""Residual-vs-fitted diagnostic uses the actual paired fit, not a new regression."""
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest

from fitting_core import fit_linear, fit_polynomial, predict_with_flags
from visualization_core import MAX_CHART_ROWS, build_chart, render_png


def test_residuals_match_actual_linear_fit_after_invalid_rows_and_weights():
    x = np.array([0, 1, np.nan, 2, 3, 4])
    y = np.array([1.2, 2.8, 99, 5.1, 6.7, 9.2])
    fit = fit_linear(x, y, weights=[1, 2, 1, 4, 3, 1])
    frame = pd.DataFrame({"x": x, "y": y})
    chart = build_chart("residuals_vs_fitted", frame,
                        {"x": "x", "y": "y", "unit_y": "V", "fit_result": fit})
    expected = predict_with_flags(fit, fit.x_fit)["predicted"]
    assert chart.valid and chart.n_rows == 5
    assert chart.frame["x"].tolist() == pytest.approx(expected)
    assert chart.frame["residual"].tolist() == pytest.approx(fit.residuals)
    assert chart.frame["x"].to_numpy() + chart.frame["residual"].to_numpy() == pytest.approx(y[[0, 1, 3, 4, 5]])
    assert chart.chart.to_dict()["layer"][0]["encoding"]["x"]["title"] == "Fitted y (V)"
    assert "does not prove" in chart.notes[0]
    assert render_png("residuals_vs_fitted", frame, {"x": "x", "y": "y", "fit_result": fit}).startswith(b"\x89PNG")


def test_polynomial_and_failed_fit_behaviour():
    x = np.arange(6, dtype=float)
    y = x * x + np.array([0.1, -0.2, 0.1, 0, 0.3, -0.2])
    fit = fit_polynomial(x, y, degree=2)
    frame = pd.DataFrame({"x": x, "y": y})
    chart = build_chart("residuals_vs_fitted", frame, {"x": "x", "y": "y", "fit_result": fit})
    assert chart.frame["x"].tolist() == pytest.approx(predict_with_flags(fit, x)["predicted"])
    failed = fit_linear([1, 1], [2, 3])
    unavailable = build_chart("residuals_vs_fitted", frame, {"x": "x", "y": "y", "fit_result": failed})
    assert not unavailable.valid and "Fit a model" in unavailable.reason


def test_large_residual_plot_is_bounded_and_disclosed():
    x = np.arange(MAX_CHART_ROWS + 1, dtype=float)
    fit = fit_linear(x, 2 * x + 1)
    chart = build_chart("residuals_vs_fitted", pd.DataFrame(), {"x": "x", "y": "y", "fit_result": fit})
    assert chart.n_rows == MAX_CHART_ROWS
    assert any("first 50,000" in warning for warning in chart.warnings)


def test_streamlit_new_plot_uses_uploaded_data_and_exports(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    root = Path(__file__).resolve().parents[1]
    at = AppTest.from_file(str(root / "general_app.py"), default_timeout=180).run()
    at.file_uploader[0].set_value(("test.csv", b"time,signal\n0,1\n1,3\n2,4\n3,8\n4,9\n", "text/csv")).run()
    next(s for s in at.selectbox if s.label == "Primary chart").set_value("residuals_vs_fitted").run()
    assert not at.exception and not at.error
    proto = at.get("vega_lite_chart")[0].proto
    spec = json.loads(proto.spec)
    chart_data = pa.ipc.open_stream(io.BytesIO(proto.datasets[0].data.data)).read_all().to_pandas()
    fit = fit_linear([0, 1, 2, 3, 4], [1, 3, 4, 8, 9])
    assert chart_data["x"].tolist() == pytest.approx(predict_with_flags(fit, fit.x_fit)["predicted"])
    assert chart_data["residual"].tolist() == pytest.approx(fit.residuals)
    assert spec["layer"][0]["encoding"]["x"]["title"] == "Fitted signal"
    assert len(at.get("download_button")) == 3
