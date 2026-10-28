"""Analytical and regression checks for conditional linear intervals."""
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import t

from fitting_core import fit_linear, fit_polynomial
from result_schema import build_result, export_bundle
from uncertainty_engine import linear_parameter_intervals


def result(fit, roles=None):
    return build_result(source={}, roles=roles or {}, cleaning={}, statistics={}, correlation={},
                        outliers={}, fit=fit, model_comparison=[], model_suggestions=[], domain={}, chart_summaries=[])


def test_analytical_ols_intervals():
    # Orthogonal residuals [1,-1,-1,1] about y=2x+1 give SSE=4, df=2, Sxx=5.
    fit = fit_linear([0, 1, 2, 3], [2, 2, 4, 8])
    block = linear_parameter_intervals(fit.as_dict(), {"unit_x": "s", "unit_y": "V"})
    assert block["status"] == "conditional" and block["degrees_of_freedom"] == 2
    assert block["critical_value"] == pytest.approx(t.ppf(.975, 2))
    slope, intercept = block["parameters"]
    assert slope["estimate"] == pytest.approx(2)
    assert slope["standard_error"] == pytest.approx(np.sqrt(0.4))
    assert slope["lower"] == pytest.approx(2 - t.ppf(.975, 2) * np.sqrt(0.4))
    assert slope["upper"] == pytest.approx(2 + t.ppf(.975, 2) * np.sqrt(0.4))
    assert slope["unit"] == "V/s" and slope["evidence"][0] == "fit.parameters.slope"
    assert intercept["estimate"] == pytest.approx(1)
    assert intercept["standard_error"] == pytest.approx(np.sqrt(1.4))
    assert intercept["unit"] == "V"
    assert "not prediction intervals" in block["limitations"]


@pytest.mark.parametrize("fit", [
    fit_linear([0, 1], [1, 3]),
    fit_linear([1, 1, 1], [1, 2, 3]),
    fit_linear([0, 1, 2, 3], [1, 2, 3, 4], weights=[1, 1, 1, 1]),
    fit_polynomial([0, 1, 2, 3, 4], [1, 2, 5, 10, 17], degree=2),
])
def test_inapplicable_fits_are_not_reported(fit):
    block = linear_parameter_intervals(fit.as_dict())
    assert block["status"] == "unavailable" and block["reason"] and not block["parameters"]


def test_invalid_standard_error_and_nonfinite_input_are_rejected():
    fit = fit_linear([0, 1, 2, 3], [2, 2, 4, 8]).as_dict()
    fit["parameter_errors"]["slope"] = float("inf")
    assert linear_parameter_intervals(fit)["status"] == "unavailable"
    fit["parameter_errors"]["slope"] = -1
    assert linear_parameter_intervals(fit)["status"] == "unavailable"


def test_json_and_markdown_export_include_same_intervals_and_escape_units():
    fit = fit_linear([0, 1, 2, 3], [2, 2, 4, 8])
    out = result(fit, {"unit_x": "s", "unit_y": "<img src=x>"})
    files = export_bundle(out)
    assert json.loads(files["results.json"])["uncertainty"] == out["uncertainty"]
    report = files["report.md"].decode()
    assert "Conditional linear parameter confidence intervals" in report
    assert "<img" not in report and "not prediction intervals" in report


def test_streamlit_sample_shows_conditional_interval_without_ai(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    assert not at.exception and not at.error
    assert any("95% Student-t intervals" in item.value for item in at.caption)
    assert any("not prediction intervals" in item.value for item in at.caption)
    assert len(at.get("download_button")) == 3
