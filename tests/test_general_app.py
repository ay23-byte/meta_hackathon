"""End-to-end tests for general_app.py using Streamlit's AppTest runner."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "general_app.py"


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    yield


def run_app(**kwargs):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=180, **kwargs).run()


def test_sample_workflow_renders_without_exceptions():
    at = run_app()
    assert not at.exception
    assert not at.error
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Valid measurements"] == "11"
    assert metrics["Slope (ΔV / ΔI)"] == "4.99091"
    assert metrics["R²"] == "0.999803"
    assert len(at.get("download_button")) == 3
    # Live AI and the explicitly labelled offline MOCK are separate actions:
    # a mock can never be silently substituted for a provider response.
    assert len(at.button) == 2
    assert at.button[0].label == "Generate evidence-grounded interpretation"
    assert "OFFLINE MOCK" in at.button[1].label and "NOT AI" in at.button[1].label


def test_provider_status_is_shown_when_no_key():
    at = run_app()
    sidebar_info = [item.value for item in at.sidebar.info]
    assert any("not configured" in text for text in sidebar_info)


def test_no_key_ai_warns_and_still_exports(monkeypatch):
    import ask_muse

    def forbidden(**kwargs):
        raise AssertionError("No provider client may be created without a key.")

    monkeypatch.setattr(ask_muse, "OpenAI", forbidden)
    at = run_app()
    at.button[0].click().run()
    assert not at.exception
    assert any("BASETEN_API_KEY is not set" in item.value for item in at.warning)
    assert len(at.get("download_button")) == 3


def test_ai_report_uses_computed_context_and_validates_schema(monkeypatch):
    import ask_muse

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    calls = []

    def fake_generate(context, section_titles=None):
        calls.append((context, section_titles))
        return {"model": "test-model", "structured": {"sections": [
            {"title": title, "content": f"Evidence note {i}."}
            for i, title in enumerate(section_titles or ask_muse.REQUIRED_TITLES)
        ], "claims": []}}

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_generate)
    at = run_app()
    at.button[0].click().run()
    assert not at.exception
    assert len(calls) == 1
    context, titles = calls[0]
    assert context["fit"]["success"] is True
    assert context["fit"]["parameters"]["slope"] == pytest.approx(4.990909, abs=1e-5)
    assert titles == list(ask_muse.REQUIRED_TITLES)
    assert any("Muse Spark report" in item.value for item in at.get("markdown"))
    assert "Evidence note 0." in [item.value for item in at.get("text")]


def test_incomplete_ai_report_is_rejected(monkeypatch):
    import ask_muse

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    monkeypatch.setattr(ask_muse, "generate_interpretation",
                        lambda context, section_titles=None: {
                            "model": "m", "structured": {"sections": [], "claims": []}})
    at = run_app()
    at.button[0].click().run()
    assert not at.exception
    assert any("incomplete report" in item.value for item in at.error)


def test_provider_failure_never_leaks_the_key(monkeypatch):
    import ask_muse

    secret = "unit-test-placeholder-key"
    monkeypatch.setenv("BASETEN_API_KEY", secret)

    def failing(context, section_titles=None):
        raise RuntimeError(f"connection failed using {secret}")

    monkeypatch.setattr(ask_muse, "generate_interpretation", failing)
    at = run_app()
    at.button[0].click().run()
    assert not at.exception
    errors = [item.value for item in at.error]
    assert any("Muse Spark request failed" in text for text in errors)
    assert all(secret not in text for text in errors)


def test_different_column_csv_upload_and_role_change():
    csv = (b"elapsed_s;intensity_mV;sigma;batch\n"
           b"0;1.1;0.1;A\n1;2.9;0.1;A\n2;5.2;0.1;B\n3;6.8;0.1;B\n4;9.1;0.1;A\n5;10.8;0.1;B\n")
    at = run_app()
    at.file_uploader[0].set_value(("other.csv", csv, "text/csv")).run()
    assert not at.exception
    assert not at.error
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Rows uploaded"] == "6"
    assert metrics["Valid measurements"] == "6"
    labels = {widget.label: widget.value for widget in at.selectbox}
    assert labels["X column (independent)"] == "elapsed_s"
    assert labels["Y column (dependent)"] == "intensity_mV"

    # Change X to a different numeric column; the app must not crash.
    for widget in at.selectbox:
        if widget.label == "X column (independent)":
            widget.set_value("sigma")
    at.run()
    assert not at.exception


def test_messy_csv_reports_cleaning_and_keeps_invalid_rows():
    # Build cp1252 bytes at test time so a tooling round-trip cannot corrupt a
    # checked-in non-UTF-8 fixture (see docs/AGENT_WORKFLOW.md, known issue).
    text = (
        "temperature_deg\u00b0C;pressure_kPa;replicate\n"
        "20.0;101.3;R1\n25.0;103.8;R1\n30.0;oops;R2\n35.0;108.1;R2\n"
        ";110.4;R3\n45.0;inf;R3\n50.0;114.7;R4\n55.0;117.2;R4\n"
    )
    raw = text.encode("cp1252")
    at = run_app()
    at.file_uploader[0].set_value(("messy.csv", raw, "text/csv")).run()
    assert not at.exception
    assert not at.error
    captions = [item.value for item in at.get("caption")]
    assert any("cp1252" in text for text in captions)
    assert any("invalid" in text.lower() for text in captions)


def test_invalid_candidate_values_are_reported():
    at = run_app()
    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value("nan, 1")
    at.run()
    assert not at.exception
    assert any("NaN and infinity are not allowed" in item.value for item in at.error)

    at = run_app()
    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value("not-a-number")
    at.run()
    assert any("Enter finite numeric values" in item.value for item in at.error)


def test_too_many_candidates_are_bounded():
    at = run_app()
    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value(", ".join(str(float(i) / 10) for i in range(80)))
    at.run()
    assert not at.exception
    assert any("Only the first 50 candidate values" in item.value for item in at.info)


def test_all_in_range_candidates_show_no_extrapolation_note():
    at = run_app()
    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value("0, 0.5, 1")
    at.run()
    assert not at.exception
    assert any("within the measured range" in item.value for item in at.info)


def test_model_and_domain_can_be_changed_without_errors():
    at = run_app()
    for widget in at.selectbox:
        if widget.label == "Model":
            widget.set_value("polynomial")
        if widget.label == "Domain interpretation layer":
            widget.set_value("ohmic")
    at.run()
    assert not at.exception
    assert not at.error
    assert any("polynomial" in item.value.lower() for item in at.get("caption"))


def test_export_bundle_matches_current_configuration():
    at = run_app()
    downloads = {item.label for item in at.get("download_button")}
    assert downloads == {
        "Download cleaned data (CSV)",
        "Download results (JSON)",
        "Download full bundle (ZIP)",
    }
    report_preview = " ".join(item.value for item in at.get("code"))
    assert "current_A" in report_preview
    assert "Schema version: 2.0" in report_preview


def test_bundled_growth_example_is_selectable():
    at = run_app()
    for widget in at.selectbox:
        if widget.label == "Or load a bundled synthetic example":
            widget.set_value("synthetic_growth.csv")
    at.run()
    assert not at.exception
    assert not at.error
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Rows uploaded"] == "15"


def test_weighted_fit_and_ohmic_domain_can_be_selected_in_ui():
    at = run_app()
    for widget in at.selectbox:
        if widget.label == "Or load a bundled synthetic example":
            widget.set_value("synthetic_calibration.csv")
    at.run()
    assert not at.exception and not at.error

    for widget in at.selectbox:
        if widget.label == "Uncertainty column (1 sigma)":
            widget.set_value("abs_sigma")
        if widget.label == "Domain interpretation layer":
            widget.set_value("calibration")
    at.run()
    assert not at.exception
    assert not at.error
    report_preview = " ".join(item.value for item in at.get("code"))
    assert "sensitivity" in report_preview
    assert "weighted: True" in report_preview


def test_original_sample_with_ohmic_layer_reports_candidate_resistance():
    at = run_app()
    for widget in at.selectbox:
        if widget.label == "Domain interpretation layer":
            widget.set_value("ohmic")
    at.run()
    assert not at.exception and not at.error
    report_preview = " ".join(item.value for item in at.get("code"))
    assert "electrical resistance (candidate)" in report_preview
    assert "ohm" in report_preview
    assert "HYPOTHESIS" in report_preview


def test_offline_mock_button_is_labelled_and_never_calls_provider(monkeypatch):
    import ask_muse

    def forbidden(**kwargs):
        raise AssertionError("The offline mock must never construct a provider client.")

    monkeypatch.setattr(ask_muse, "OpenAI", forbidden)
    at = run_app()
    assert len(at.button) == 2
    at.button[1].click().run()
    assert not at.exception
    assert not at.error
    assert any("OFFLINE MOCK report" in item.value for item in at.get("markdown"))
    assert any("NOT AI" in item.value for item in at.warning)
    preview = " ".join(item.value for item in at.get("code"))
    assert "OFFLINE MOCK report" in preview
    assert "is_mock" not in preview  # report.md labels it in prose, not raw JSON
