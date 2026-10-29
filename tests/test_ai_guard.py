"""The numeric guard is bounded and never claims general fact checking."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

import ask_muse
from ai_guard import check_report_numbers

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {"result_ids": ["fit.linear"], "fit": {"parameters": {"slope": 2.5, "intercept": 0.1},
           "metrics": {"r2": 0.987654, "rmse": 0.123456}, "n_observations": 12}}


def report(text, ids=None):
    return {"sections": [{"title": "Quantitative Results", "content": text}],
            "claims": [{"claim": text, "evidence_ids": ids if ids is not None else ["fit.linear"]}]}


def test_valid_rounded_values_are_only_partially_checked():
    result = check_report_numbers(report("slope=2.5; R²=0.98765; RMSE=0.12346; n=12"), CONTEXT)
    assert result["status"] == "partially_checked"
    assert len(result["checked"]) == 8
    assert "not verified" in result["limitations"]
    assert result["unverified"]


def test_contradictions_and_nonexistent_ids_are_detected():
    assert check_report_numbers(report("slope=250"), CONTEXT)["status"] == "contradiction"
    assert check_report_numbers(report("slope=2.5", ["fit.other"]), CONTEXT)["status"] == "contradiction"
    assert check_report_numbers(report("slope=2.5", []), CONTEXT)["status"] == "contradiction"
    assert check_report_numbers(report("intercept=0"), CONTEXT)["status"] == "contradiction"


def test_unsupported_numbers_units_and_citations_remain_unverified():
    result = check_report_numbers(report("Temperature was 37 K, doi 10.0000/example."), CONTEXT)
    assert result["status"] == "partially_checked" and not result["checked"]
    assert "Units, citations" in result["limitations"]


def test_ui_rejects_fabricated_fit_number_without_losing_deterministic_results(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    def fake_live(context, section_titles=None, **kwargs):
        sections = [{"title": title, "content": "The slope = 999999." if i == 0 else "Inspect the data."}
                    for i, title in enumerate(section_titles or ask_muse.REQUIRED_TITLES)]
        return {"model": "test-model", "structured": {"sections": sections, "claims": []}}
    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_live)
    app = AppTest.from_file(str(ROOT / "general_app.py"), default_timeout=120).run()
    next(button for button in app.button if button.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception
    assert any("Report rejected" in error.value for error in app.error)
    assert len(app.get("download_button")) == 3
    assert any("Slope =" in item.value for item in app.text)
