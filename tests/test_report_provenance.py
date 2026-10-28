"""Provenance-aware report reuse in general_app.py.

Regression for the bug where an OFFLINE MOCK report for the current analysis
blocked the live Muse Spark button. Live and mock reports are now stored
separately and reused only by the action with matching provenance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ask_muse

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "general_app.py"
FAKE_KEY = "sk-unit-test-fake-key-0000"
LIVE_BUTTON = "Generate evidence-grounded interpretation"
MOCK_BUTTON = "Preview deterministic OFFLINE MOCK report"


def run_app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=180).run()


def click_button(at, prefix):
    matches = [button for button in at.button if button.label.startswith(prefix)]
    assert len(matches) == 1, f"Expected one button starting with {prefix!r}"
    matches[0].click().run()


def values(at, element_type):
    return [item.value for item in at.get(element_type)]


def live_wrapper():
    """A valid live-provider-shaped response without provenance fields.

    The app must stamp explicit live provenance before storing it.
    """
    return {
        "model": "meta-models/muse-spark-open",
        "structured": {
            "sections": [
                {"title": title, "content": f"Live evidence note {index}."}
                for index, title in enumerate(ask_muse.REQUIRED_TITLES)
            ],
            "claims": [],
        },
    }


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------

def test_report_kind_and_enforce_report_provenance():
    plain = live_wrapper()
    assert ask_muse.report_kind(plain) == "unknown"

    live = ask_muse.enforce_report_provenance(plain, "live")
    assert ask_muse.report_kind(live) == "live"
    assert live["source"] == ask_muse.LIVE_REPORT_SOURCE
    assert live["is_mock"] is False
    assert live["provider_status"] == "live_response_validated"
    assert "disclaimer" not in live

    mock = ask_muse.enforce_report_provenance(plain, "mock")
    assert ask_muse.report_kind(mock) == "mock"
    assert mock["source"] == ask_muse.MOCK_REPORT_SOURCE
    assert mock["is_mock"] is True
    assert mock["provider_status"] == "not_called"
    assert "NOT AI" in mock["disclaimer"]

    with pytest.raises(RuntimeError, match="offline MOCK"):
        ask_muse.enforce_report_provenance(mock, "live")
    with pytest.raises(ValueError, match=r"live.*mock"):
        ask_muse.enforce_report_provenance(plain, "unknown")


# ---------------------------------------------------------------------------
# Streamlit workflow regressions
# ---------------------------------------------------------------------------

def test_mock_does_not_block_a_live_provider_request(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []

    def fake_live(context, section_titles=None, **kwargs):
        calls.append((context, section_titles))
        return live_wrapper()

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_live)
    at = run_app()

    click_button(at, MOCK_BUTTON)
    assert any("OFFLINE MOCK report" in text for text in values(at, "markdown"))
    assert at.session_state["ai_state"]["active"] == "mock"

    click_button(at, LIVE_BUTTON)
    assert len(calls) == 1
    assert not at.exception
    assert any("Muse Spark report" in text for text in values(at, "markdown"))
    assert not any("OFFLINE MOCK report" in text for text in values(at, "markdown"))
    state = at.session_state["ai_state"]
    assert state["active"] == "live"
    assert state["live"]["source"] == ask_muse.LIVE_REPORT_SOURCE
    assert state["live"]["is_mock"] is False
    assert state["live"]["provider_status"] == "live_response_validated"
    assert state["mock"]["source"] == ask_muse.MOCK_REPORT_SOURCE


def test_existing_live_report_for_unchanged_analysis_is_reused(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []

    def fake_live(context, section_titles=None, **kwargs):
        calls.append(context)
        return live_wrapper()

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_live)
    at = run_app()
    click_button(at, LIVE_BUTTON)
    click_button(at, LIVE_BUTTON)

    assert not at.exception
    assert len(calls) == 1
    assert any("no duplicate provider request" in text for text in values(at, "info"))
    assert at.session_state["ai_state"]["active"] == "live"


def test_live_failure_shows_error_and_never_presents_mock_as_live(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    mock_calls = []
    original_mock = ask_muse.generate_mock_report

    def counting_mock(*args, **kwargs):
        mock_calls.append(1)
        return original_mock(*args, **kwargs)

    def failing_live(context, section_titles=None, **kwargs):
        raise RuntimeError(f"provider unavailable while using {FAKE_KEY}")

    monkeypatch.setattr(ask_muse, "generate_mock_report", counting_mock)
    monkeypatch.setattr(ask_muse, "generate_interpretation", failing_live)
    at = run_app()

    click_button(at, MOCK_BUTTON)
    assert len(mock_calls) == 1
    assert any("OFFLINE MOCK report" in text for text in values(at, "markdown"))

    click_button(at, LIVE_BUTTON)
    assert not at.exception
    assert len(mock_calls) == 1  # no silent mock fallback/regeneration
    errors = values(at, "error")
    assert any("Muse Spark request failed" in text for text in errors)
    assert all(FAKE_KEY not in text for text in errors)
    assert any("NOT substituted" in text for text in values(at, "info"))
    assert not any("Muse Spark report" in text for text in values(at, "markdown"))
    assert not any("OFFLINE MOCK report" in text for text in values(at, "markdown"))
    assert any("AI status: failed" in text for text in values(at, "caption"))
    state = at.session_state["ai_state"]
    assert state["active"] is None
    assert state["live"] is None
    assert state["mock"] is not None  # preserved only for an explicit later mock click


def test_mock_button_never_calls_the_provider_without_a_key(monkeypatch):
    live_calls = []

    def forbidden_live(*args, **kwargs):
        live_calls.append(1)
        raise AssertionError("The mock button must never call generate_interpretation.")

    def forbidden_openai(*args, **kwargs):
        live_calls.append(1)
        raise AssertionError("The mock button must never construct an OpenAI client.")

    monkeypatch.setattr(ask_muse, "generate_interpretation", forbidden_live)
    monkeypatch.setattr(ask_muse, "OpenAI", forbidden_openai)
    at = run_app()
    click_button(at, MOCK_BUTTON)

    assert not at.exception
    assert not at.error
    assert live_calls == []
    assert any("OFFLINE MOCK report" in text for text in values(at, "markdown"))
    assert any("NOT AI" in text for text in values(at, "warning"))
    state = at.session_state["ai_state"]
    assert state["active"] == "mock"
    assert state["live"] is None
    assert state["mock"]["source"] == ask_muse.MOCK_REPORT_SOURCE


def test_changing_analysis_context_invalidates_both_reports(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []

    def fake_live(context, section_titles=None, **kwargs):
        calls.append(context)
        return live_wrapper()

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_live)
    at = run_app()
    click_button(at, LIVE_BUTTON)
    click_button(at, MOCK_BUTTON)
    assert len(calls) == 1
    assert any("OFFLINE MOCK report" in text for text in values(at, "markdown"))

    old_hash = at.session_state["ai_context_hash"]
    question_inputs = [widget for widget in at.text_input
                       if widget.label == "Scientific question"]
    assert len(question_inputs) == 1
    question_inputs[0].set_value("A different research question")
    at.run()

    assert at.session_state["ai_context_hash"] != old_hash
    assert not any("Muse Spark report" in text for text in values(at, "markdown"))
    assert not any("OFFLINE MOCK report" in text for text in values(at, "markdown"))
    assert at.session_state.get("ai_state") is None

    click_button(at, LIVE_BUTTON)
    assert len(calls) == 2
    assert any("Muse Spark report" in text for text in values(at, "markdown"))
    assert at.session_state["ai_state"]["active"] == "live"


def test_legacy_app_does_not_reuse_a_mock_as_a_live_report(monkeypatch):
    """The older app.py workflow must obey the same provenance boundary."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []

    def fake_generate(context, section_titles=None, **kwargs):
        calls.append(context)
        return ask_muse.enforce_report_provenance(live_wrapper(), "live")

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_generate)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    click_button(at, LIVE_BUTTON)
    assert len(calls) == 1
    assert any("Muse Spark report" in text for text in values(at, "markdown"))

    # Simulate a stored mock wrapper for the same analysis hash.
    stored = dict(at.session_state["lablens_ai_report"])
    stored.update({
        "source": ask_muse.MOCK_REPORT_SOURCE,
        "is_mock": True,
        "provider_status": "not_called",
    })
    at.session_state["lablens_ai_report"] = stored
    at.run()
    assert not any("Muse Spark report" in text for text in values(at, "markdown"))

    click_button(at, LIVE_BUTTON)
    assert not at.exception
    assert len(calls) == 2
    assert any("Muse Spark report" in text for text in values(at, "markdown"))
    assert at.session_state["lablens_ai_report"]["source"] == \
        ask_muse.LIVE_REPORT_SOURCE
