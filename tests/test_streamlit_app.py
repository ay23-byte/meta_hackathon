"""End-to-end UI tests using Streamlit's AppTest runner.

These execute the real app script (with the bundled sample dataset) without
a browser or network access. They verify that the dashboard renders, that
the no-key AI path is safe, and that bad input does not break exports.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def valid_ai_wrapper():
    import ask_muse

    return {
        "model": "meta-models/muse-spark-open",
        "structured": {
            "sections": [
                {"title": title, "content": f"Evidence note for {index}."}
                for index, title in enumerate(ask_muse.REQUIRED_TITLES)
            ],
            "claims": [
                {
                    "claim": "The slope is positive.",
                    "evidence": "Computed OLS slope.",
                    "evidence_type": "computed_result",
                    "confidence_or_uncertainty": "Not calibrated.",
                    "limitation": "Eleven points only.",
                    "proposed_verification": "Collect more data.",
                }
            ],
        },
    }


def run_app(**kwargs):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=60, **kwargs).run()


def all_caption_text(at):
    texts = [element.value for element in at.get("caption")]
    for block in (at, at.sidebar):
        try:
            texts.extend(element.value for element in block.caption)
        except (AttributeError, TypeError):
            pass
    return "\n".join(texts)


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    # A stale .env in a developer checkout must not turn unit tests into
    # live API calls; the app loads .env at import time.
    yield


def test_dashboard_renders_sample_without_exceptions():
    at = run_app()

    assert not at.exception
    assert not at.error

    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Valid measurements"] == "11"
    assert metrics["Slope (ΔV / ΔI)"] == "4.99091 V/A"
    assert metrics["R²"] == "0.999803"
    assert len(at.get("download_button")) == 3

    captions = all_caption_text(at)
    assert "Built with Muse Spark Open" in captions
    assert "inference.baseten.co/v1" in captions


def test_ai_button_without_key_warns_and_never_contacts_provider(monkeypatch):
    import ask_muse

    def forbidden(**kwargs):
        raise AssertionError("No provider client may be created without a key.")

    monkeypatch.setattr(ask_muse, "OpenAI", forbidden)

    at = run_app()
    at.button[0].click().run()

    assert not at.exception
    warnings = [warning.value for warning in at.warning]
    assert any("BASETEN_API_KEY is not set" in text for text in warnings)
    assert len(at.get("download_button")) == 3


def test_invalid_explorer_values_show_error_but_keep_exports():
    at = run_app()

    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value("not-a-number, 2")
    at.run()

    assert not at.exception
    assert any("Enter finite numeric values" in text.value for text in at.error)
    assert len(at.get("download_button")) == 3


def test_too_many_candidate_values_are_bounded():
    at = run_app()

    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value(", ".join(str(float(i) / 10) for i in range(80)))
    at.run()

    assert not at.exception
    infos = [info.value for info in at.info]
    assert any("Only the first 50 candidate values are used" in text for text in infos)


def test_sidebar_reports_provider_configuration_state():
    at = run_app()
    sidebar_info = [info.value for info in at.sidebar.info]
    assert any("not configured" in text for text in sidebar_info)
    assert os.getenv("BASETEN_API_KEY") is None


def test_valid_ai_report_is_rendered_as_plain_text(monkeypatch):
    import ask_muse

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    calls = []

    def fake_generate(context):
        calls.append(context)
        return valid_ai_wrapper()

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_generate)

    at = run_app()
    at.button[0].click().run()

    assert not at.exception
    assert len(calls) == 1
    assert "results" in calls[0]
    assert any("Muse Spark report" in text.value for text in at.markdown)
    section_text = [text.value for text in at.get("text")]
    assert "Evidence note for 0." in section_text
    assert any("Evidence-linked claims" in text.value for text in at.markdown)
    assert len(at.get("download_button")) == 3


def test_ai_report_is_invalidated_when_the_analysis_context_changes(monkeypatch):
    import ask_muse

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    monkeypatch.setattr(
        ask_muse, "generate_interpretation", lambda context: valid_ai_wrapper()
    )

    at = run_app()
    at.button[0].click().run()
    assert any("Muse Spark report" in text.value for text in at.markdown)

    for widget in at.text_input:
        if widget.label == "Scientific question":
            widget.set_value("A different scientific question")
    at.run()

    assert not at.exception
    assert not any("Muse Spark report" in text.value for text in at.markdown)


def test_incomplete_ai_report_is_rejected_in_the_ui(monkeypatch):
    import ask_muse

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    monkeypatch.setattr(
        ask_muse,
        "generate_interpretation",
        lambda context: {"model": "m", "structured": {"sections": [], "claims": []}},
    )

    at = run_app()
    at.button[0].click().run()

    assert not at.exception
    assert any("incomplete report" in text.value for text in at.error)
    assert not any("Muse Spark report" in text.value for text in at.markdown)


def upload(csv_bytes, name="upload.csv"):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.file_uploader[0].set_value((name, csv_bytes, "text/csv")).run()
    return at


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"current_A,voltage_V\n", "no usable rows or columns"),
        (b"current_A,voltage_V\n\xff\xfe,1\n", "Could not read"),
        (b"current_A,voltage_V\n0,1\nbad,2\n", "At least two valid paired"),
        (
            b"current_A,voltage_V\n1,1\n1,2\n1,3\n",
            "Current measurements must vary",
        ),
    ],
)
def test_bad_uploads_fail_with_clear_messages(content, expected):
    at = upload(content)
    assert not at.exception
    assert any(expected in text.value for text in at.error)
    assert len(at.get("download_button")) == 0


def test_same_column_selection_is_rejected():
    at = run_app()
    for widget in at.selectbox:
        if widget.label == "Voltage column":
            widget.set_value("current_A")
    at.run()
    assert not at.exception
    assert any(
        "Choose different columns" in text.value for text in at.error
    )


def test_small_dataset_surfaces_data_quality_warnings():
    at = upload(b"current_A,voltage_V\n0,1\nbad,2\n1,3\n")
    warnings = [text.value for text in at.warning]
    assert not at.exception
    assert any("Only two measurements remain" in text for text in warnings)
    assert any("Fewer than three distinct current" in text for text in warnings)
    assert any("Few valid measurements remain" in text for text in warnings)
    assert any("Invalid selected measurements were excluded" in text for text in all_caption_text(at).splitlines())


def test_constant_voltage_upload_reports_undefined_r_squared():
    at = upload(b"current_A,voltage_V\n0,5\n1,5\n2,5\n")
    assert not at.exception
    assert any(
        "Voltage has no observed variation" in text.value for text in at.warning
    )
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["R²"] == "Undefined"


def test_upload_row_and_byte_limits_are_enforced():
    many_rows = b"current_A,voltage_V\n" + b"0.1,0.5\n" * 200_001
    at = upload(many_rows, "too_many_rows.csv")
    assert not at.exception
    assert any("row limit" in text.value for text in at.error)

    padded_row = b"0.123456789,0.987654321," + b"p" * 50 + b"\n"
    oversized = b"current_A,voltage_V,padding\n" + padded_row * 90_000
    at = upload(oversized, "too_big.csv")
    assert not at.exception
    assert any("byte limit" in text.value for text in at.error)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", "Enter at least one candidate"),
        ("nan, 1", "NaN and infinity are not allowed"),
    ],
)
def test_bad_candidate_inputs_are_reported(value, expected):
    at = run_app()
    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value(value)
    at.run()
    assert not at.exception
    assert any(expected in text.value for text in at.error)


def test_all_in_range_candidates_show_the_no_extrapolation_note():
    at = run_app()
    for widget in at.text_input:
        if widget.label.startswith("Candidate current"):
            widget.set_value("0, 0.5, 1")
    at.run()
    assert not at.exception
    assert any(
        "All proposed points are within the measured range" in info.value
        for info in at.info
    )


def test_provider_failure_is_shown_without_leaking_the_key(monkeypatch):
    import ask_muse

    secret = "unit-test-placeholder-key"
    monkeypatch.setenv("BASETEN_API_KEY", secret)

    def failing(context):
        raise RuntimeError(f"connection failed using {secret}")

    monkeypatch.setattr(ask_muse, "generate_interpretation", failing)

    at = run_app()
    at.button[0].click().run()

    assert not at.exception
    errors = [text.value for text in at.error]
    assert any("Muse Spark request failed" in text for text in errors)
    assert all(secret not in text for text in errors)
    assert len(at.get("download_button")) == 3
