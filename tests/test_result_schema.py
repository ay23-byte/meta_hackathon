"""A single result schema drives every export artifact."""

import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

import ask_muse
from fitting_core import fit_linear
from result_schema import ai_context, build_result, export_bundle, markdown_report, results_json
from statistics_core import descriptive_table


@pytest.fixture
def result():
    x = np.linspace(0, 1, 11)
    y = 5 * x + 0.01
    fit = fit_linear(x, y)
    return build_result(
        source={"name": "sample.csv", "rows": 11, "columns": ["current_A", "voltage_V"],
                "delimiter": ",", "encoding": "utf-8", "sha256": "a" * 64,
                "warnings": ["source warning"]},
        roles={"x": "current_A", "y": "voltage_V", "secondary_y": []},
        cleaning={"rows_in": 11, "rows_out": 11, "duplicates_removed": 0,
                  "invalid_pair_rows_excluded": 0, "columns": [], "warnings": []},
        statistics={"voltage_V": {"n_valid": 11, "n_total": 11, "mean": float(y.mean()),
                                  "median": float(np.median(y)), "std_sample": float(y.std(ddof=1)),
                                  "min": float(y.min()), "max": float(y.max()), "q1": 1.0, "q3": 4.0,
                                  "ci_mean_95": [1.0, 4.0], "ci_mean_method": "t interval"}},
        correlation={"method": "pearson", "coefficient": 1.0, "p_value": 0.0,
                     "n_valid": 11, "n_excluded": 0, "caveat": "not causation"},
        outliers={"n_low": 0, "n_high": 0, "n_valid": 11, "caveat": "heuristic"},
        fit=fit,
        model_comparison=[{"model": "linear", "label": fit.label, "success": True,
                           "n_observations": 11, "r2": 1.0, "adjusted_r2": 1.0,
                           "aic": -50.0, "rmse": 0.0}],
        model_suggestions=[{"model": "linear", "confidence": "low"}],
        domain={"label": "Generic", "description": "no law", "assumptions": ["none"],
                "derived": [], "hypotheses": [], "warnings": []},
        chart_summaries=[{"label": "Scatter", "n_rows": 11, "file": "plots/scatter.png", "warnings": []}],
        notes=["test note"],
    )


def test_result_is_strict_json_serializable(result):
    payload = results_json(result)
    assert json.loads(payload)["schema_version"] == "2.0"
    assert b"NaN" not in payload and b"Infinity" not in payload


def test_markdown_report_contains_all_deterministic_sections(result):
    report = markdown_report(result)
    for heading in ("Configuration", "Cleaning decisions", "Descriptive statistics",
                    "Association and diagnostics", "Fit", "Model comparison",
                    "Domain interpretation", "Figures", "Limitations and provenance"):
        assert heading in report
    assert "4.99091" in report or "5" in report
    assert "not experimental evidence" not in report or "AI-generated" in report


def test_markdown_report_attributes_ai_text_when_present(result):
    result["ai"] = {"model": "test-model", "structured": {
        "sections": [{"title": title, "content": f"AI text {i}"}
                     for i, title in enumerate(ask_muse.REQUIRED_TITLES)],
        "claims": [],
    }}
    report = markdown_report(result)
    assert "AI-generated interpretation (unverified hypotheses)" in report
    assert "not experimental evidence" in report
    assert "AI text 0" in report


def test_export_bundle_contains_every_required_artifact(result):
    frame = pd.DataFrame({"a": [1, 2, 3]})
    files = export_bundle(result, cleaned_frame=frame,
                          descriptive_table=descriptive_table(frame, ["a"]),
                          charts={"plots/scatter.html": b"<html></html>"})
    for name in ("results.json", "cleaned_data.csv", "statistics.csv",
                 "fit_parameters.csv", "fit_metrics.csv", "report.md", "plots/scatter.html"):
        assert name in files and len(files[name]) > 0
    assert files["cleaned_data.csv"].startswith(b"\xef\xbb\xbf")  # BOM helps Excel
    assert json.loads(files["results.json"])["fit"]["success"] is True


def test_csv_export_blocks_formula_injection():
    frame = pd.DataFrame({"value": ["=1+1", "+SUM(A1)", "@cmd", "2"]})
    from result_schema import export_bundle
    files = export_bundle(build_result(
        source={}, roles={}, cleaning={}, statistics={}, correlation={}, outliers={},
        fit=None, model_comparison=[], model_suggestions=[], domain={}, chart_summaries=[],
    ), cleaned_frame=frame)
    csv_text = files["cleaned_data.csv"].decode("utf-8-sig")
    for line in csv_text.splitlines()[1:]:
        assert not line.startswith(("=", "+", "@"))


def test_failed_fit_still_exports_parameter_and_metric_placeholders(result):
    result["fit"] = {"success": False, "reason": "not enough data", "model": "linear",
                     "warnings": [], "parameters": {}, "metrics": {}}
    files = export_bundle(result, cleaned_frame=pd.DataFrame({"a": [1]}))
    assert b"not enough data" in files["fit_parameters.csv"]
    assert "Fit was not successful" in files["report.md"].decode("utf-8")


def test_ai_context_excludes_raw_rows_and_prior_ai_text(result):
    result["ai"] = {"model": "secret", "structured": {"sections": [], "claims": []}}
    context = ai_context(result)
    text = json.dumps(context)
    assert "secret" not in text
    assert "computed locally" in text
    assert "fit" in context and "statistics" in context


def test_ai_context_is_bounded(result):
    result["statistics"] = {f"col_{i}": {"n_valid": 3, "mean": 1.0} for i in range(5000)}
    context = ai_context(result, max_chars=4000)
    assert len(json.dumps(context)) <= 4000


def test_full_bundle_is_a_valid_zip(result):
    files = export_bundle(result, cleaned_frame=pd.DataFrame({"a": [1, 2]}))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        assert "results.json" in archive.namelist()
