"""The Streamlit app exposes a visible, opt-in agent audit trail."""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "general_app.py"


@pytest.fixture(autouse=True)
def no_key(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    yield


def run_app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=180).run()


def test_agent_section_is_present_but_opt_in():
    at = run_app()
    assert not at.exception
    labels = [widget.label for widget in at.checkbox]
    assert any("Run the bounded analysis agent" in label for label in labels)
    assert any("Allow destructive agent tools" in label for label in labels)
    assert "Agent not run." in " ".join(item.value for item in at.get("caption"))
    # Existing UI contract stays intact; the second button is the explicitly
    # labelled offline MOCK preview (never a silent AI substitute).
    assert len(at.button) == 2
    assert "OFFLINE MOCK" in at.button[1].label
    assert len(at.get("download_button")) == 3


def test_consent_runs_agent_and_shows_audit_trail():
    at = run_app()
    for widget in at.checkbox:
        if widget.label.startswith("Run the bounded analysis agent"):
            widget.set_value(True)
    at.run()
    assert not at.exception
    assert not at.error
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics.get("Agent state") in ("DONE", "INSUFFICIENT_EVIDENCE",
                                          "NEEDS_CLARIFICATION", "FAILED")
    assert "Plan source" in metrics and "Retries" in metrics
    captions = " ".join(item.value for item in at.get("caption"))
    assert "DETERMINISTIC TOOL rows are computed results" in captions
    assert "Audit artifacts are included in the full export bundle" in captions
    assert len(at.get("download_button")) == 3


def test_destructive_consent_defaults_off():
    at = run_app()
    for widget in at.checkbox:
        if widget.label.startswith("Allow destructive agent tools"):
            assert widget.value is False


def test_agent_works_without_api_key_and_stays_offline():
    assert os.getenv("BASETEN_API_KEY") is None
    at = run_app()
    for widget in at.checkbox:
        if widget.label.startswith("Run the bounded analysis agent"):
            widget.set_value(True)
    at.run()
    assert not at.exception
    metrics = {metric.label: metric.value for metric in at.metric}
    assert "deterministic fallback" in metrics["Plan source"]


@pytest.mark.parametrize("mode", ["nvidia", "baseten", "ollama"])
def test_agent_ai_requires_button_on_each_rerun(monkeypatch, mode):
    import agent_planner
    import provider_router

    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    calls = []
    def fake_plan(prompt, **kwargs):
        calls.append(mode)
        raise RuntimeError("mock failure")
    monkeypatch.setattr(provider_router, "request_plan", fake_plan)
    monkeypatch.setattr(agent_planner, "generate_grounded_interpretation", lambda digest: None)
    at = run_app()
    next(c for c in at.checkbox if c.label.startswith("Run the bounded analysis agent")).check().run()
    next(c for c in at.checkbox if c.label.startswith("Allow selected provider")).check().run()
    assert calls == []
    next(b for b in at.button if b.label == "Run agent AI now").click().run()
    assert calls == [mode]
    at.run()
    assert calls == [mode]
    assert not at.exception
