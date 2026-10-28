"""Conditional unweighted linear prediction intervals and export behavior."""

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import t
from streamlit.testing.v1 import AppTest

from fitting_core import fit_linear, fit_model
from result_schema import export_bundle
from uncertainty_engine import linear_prediction_intervals


def test_intervals_match_analytical_reference_and_flag_extrapolation():
    x = np.array([0., 1., 2., 3., 4.])
    y = np.array([1., 2.9, 5.2, 7.1, 8.8])
    fit = fit_linear(x, y)
    answer = linear_prediction_intervals(fit, [2., 6.])
    assert answer["status"] == "conditional"
    s = np.sqrt(np.sum(fit.residuals**2) / (len(x) - 2))
    critical = t.ppf(.975, len(x) - 2)
    for row in answer["rows"]:
        leverage = 1 / len(x) + (row["candidate_x"] - x.mean()) ** 2 / np.sum((x - x.mean()) ** 2)
        assert row["mean_upper"] - row["predicted_y"] == pytest.approx(critical * s * np.sqrt(leverage))
        assert row["prediction_upper"] - row["predicted_y"] == pytest.approx(critical * s * np.sqrt(1 + leverage))
        assert row["prediction_lower"] < row["mean_lower"] < row["predicted_y"]
    assert [row["range_flag"] for row in answer["rows"]] == ["in_range", "extrapolated"]


def test_intervals_refuse_unsupported_and_invalid_inputs():
    assert linear_prediction_intervals(fit_linear([0, 1], [1, 2]), [0.5])["status"] == "unavailable"
    assert linear_prediction_intervals(fit_linear([0, 1, 2], [1, 2, 3], weights=[1, 1, 1]), [1])["status"] == "unavailable"
    nonlinear = fit_model("polynomial", [0, 1, 2, 3], [1, 2, 4, 8])
    assert linear_prediction_intervals(nonlinear, [1])["status"] == "unavailable"
    fit = fit_linear([0, 1, 2], [1, 2, 4])
    for inputs in ([], [float("nan")], list(range(51))):
        assert linear_prediction_intervals(fit, inputs)["status"] == "unavailable"


def test_prediction_export_preserves_conditions():
    fit = fit_linear([0, 1, 2, 3], [1, 3, 4, 7])
    intervals = linear_prediction_intervals(fit, [2, 9])
    result = {"predictions": {"rows": [{"candidate_x": r["candidate_x"], "predicted_y": r["predicted_y"],
                                      "range_flag": r["range_flag"]} for r in intervals["rows"]],
                              "intervals": intervals, "caveat": "Model outputs, not measurements."}}
    files = export_bundle(result)
    assert json.loads(files["results.json"])["predictions"]["intervals"] == intervals
    report = files["report.md"].decode()
    assert "individual" not in report or "prediction" in report
    assert "Conditional 95% intervals" in report and "extrapolated" in report


def test_prediction_intervals_render_in_app():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=90).run()
    candidate = next(w for w in app.text_input if w.label.startswith("Candidate"))
    candidate.set_value("0.5, 2").run()
    assert not app.exception and not app.error
    assert any(e.label.startswith("Conditional 95% mean-response") for e in app.expander)
    assert any("extrapolated" in w.value.lower() for w in app.warning)
    assert any("Follow-up predictions" in c.value for c in app.code)
