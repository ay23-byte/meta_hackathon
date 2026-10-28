"""Regression tests for independently identified audit findings."""
import numpy as np
import pandas as pd

import ask_muse
from fitting_core import compare_models, fit_linear, fit_polynomial
from result_schema import markdown_report
from statistics_core import correlation_matrix, covariance


def test_comparison_ranks_lower_aic_first():
    x = np.arange(12.0)
    y = 2 + x + 0.4 * x**2 + np.sin(x) * 0.01
    fits = [fit_linear(x, y), fit_polynomial(x, y, degree=2)]
    rows = compare_models(fits)
    assert rows[0]["model"] == "polynomial"
    assert rows[0]["aic"] < rows[1]["aic"]


def test_polynomial_rejects_rank_deficient_design():
    fit = fit_polynomial([0, 0, 1, 1, 1], [1, 2, 3, 4, 5], degree=2)
    assert not fit.success
    assert "rank deficient" in fit.reason


def test_covariance_rejects_unequal_lengths_and_nonfinite_result():
    assert not covariance([1, 2], [1])["valid"]
    with np.errstate(all="ignore"):
        result = covariance([1e308, -1e308], [1e308, -1e308])
    assert not result["valid"] and result["value"] is None


def test_constant_column_correlation_matrix_diagonal_is_undefined():
    matrix = correlation_matrix(pd.DataFrame({"constant": [1, 1, 1], "variable": [1, 2, 3]}),
                                ["constant", "variable"])
    assert np.isnan(matrix.loc["constant", "constant"])
    assert matrix.loc["variable", "variable"] == 1


def test_markdown_treats_untrusted_model_and_column_text_as_text():
    text = '<img src=x onerror=alert(1)> [click](https://example.com)'
    result = {"source": {"name": text}, "statistics": {text: {}},
              "ai": {"source": "offline_mock", "is_mock": True, "structured": {
                  "sections": [{"title": "Executive Summary", "content": text}], "claims": []}}}
    report = markdown_report(result)
    assert '<img' not in report
    assert '[click](https://example.com)' not in report
    assert '&lt;img' in report


def test_explicit_regeneration_calls_provider_again(monkeypatch):
    from test_report_provenance import click_button, live_wrapper, run_app

    monkeypatch.setenv("BASETEN_API_KEY", "sk-unit-test-fake-key-0000")
    calls = []
    def fake_live(*args, **kwargs):
        calls.append(1)
        return live_wrapper()
    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_live)
    at = run_app()
    click_button(at, "Generate evidence-grounded interpretation")
    click_button(at, "Generate evidence-grounded interpretation")
    assert len(calls) == 1
    next(box for box in at.checkbox if box.label.startswith("Regenerate live report")).check().run()
    click_button(at, "Generate evidence-grounded interpretation")
    assert len(calls) == 2
    report = at.session_state["ai_state"]["live"]
    assert report["validation_status"] == "validated"
    assert len(report["analysis_fingerprint"]) == 64
    assert report["validated_at_utc"].endswith("+00:00")


def test_cli_rejects_mock_returned_on_live_path(monkeypatch, tmp_path):
    from pathlib import Path

    import analyze_dataset

    monkeypatch.setenv("BASETEN_API_KEY", "sk-unit-test-fake-key-0000")
    monkeypatch.setattr(ask_muse, "generate_interpretation",
                        lambda context, **kwargs: ask_muse.generate_mock_report(
                            context, section_titles=kwargs.get("section_titles"), profile="legacy"))
    path = Path(__file__).resolve().parents[1] / "data" / "sample_voltage_current.csv"
    result = analyze_dataset.analyze_csv(path, tmp_path, generate_ai=True)
    assert result["ai"] is None
    assert "unavailable" in result["ai_note"]


def test_connectivity_check_makes_one_minimal_request(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("BASETEN_API_KEY", "sk-unit-test-fake-key-0000")
    calls = []
    def fake_client(**kwargs):
        assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 30.0
        def create(**request):
            calls.append(request)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ask_muse, "OpenAI", fake_client)
    ask_muse.check_provider_connectivity()
    assert len(calls) == 1
    assert calls[0]["messages"] == [{"role": "user", "content": "Reply with OK."}]


def test_connectivity_missing_key_never_constructs_client(monkeypatch):
    import pytest

    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kwargs: pytest.fail("network client constructed"))
    with pytest.raises(RuntimeError, match="not configured"):
        ask_muse.check_provider_connectivity()


def test_spreadsheet_formula_injection_protected_in_headers_cells_and_legacy_export():
    import io

    from analysis_core import serialize_analysis_exports
    from result_schema import _csv_bytes

    frame = pd.DataFrame({"=HEADER": ["  =1+1", "\t@cmd", "safe"], "x": [1, 2, 3]})
    for payload in (_csv_bytes(frame).decode("utf-8-sig"),
                    serialize_analysis_exports({}, frame, "# report")["csv"]):
        parsed = pd.read_csv(io.StringIO(payload), dtype=str)
        assert parsed.columns[0] == "'=HEADER"
        assert parsed.iloc[0, 0] == "'  =1+1"
        assert parsed.iloc[1, 0] == "'\t@cmd"
        assert parsed.iloc[2, 0] == "safe"
