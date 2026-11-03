"""Offline dispatch and fail-closed tests for the shared report router."""
import pytest

import ask_muse
import hosted_model_provider
import local_meta_provider
import provider_router


@pytest.mark.parametrize("selection,expected", [
    ("nvidia", "hosted_model"), ("baseten", "live_provider"), ("ollama", "local_ollama"),
])
def test_dispatches_only_selected_adapter(monkeypatch, selection, expected):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", selection)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-key")
    calls = []

    def adapter(name, source):
        def call(*args, **kwargs):
            calls.append(name)
            return {"source": source, "is_mock": False, "model": name,
                    "structured": {"sections": [], "claims": []}}
        return call

    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", adapter("nvidia", "hosted_model"))
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", adapter("ollama", "local_ollama"))
    monkeypatch.setattr(ask_muse, "generate_interpretation", adapter("baseten", "live_provider"))
    report = provider_router.generate_interpretation({}, confirmed=True)
    assert calls == [selection]
    assert report["source"] == expected and report["is_mock"] is False
    assert report["model"] == selection


@pytest.mark.parametrize("selection", ["nvidia", "baseten", "ollama", "unrecognized"])
def test_failure_never_calls_a_different_adapter(monkeypatch, selection):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", selection)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-key")
    calls = []

    def adapter(name):
        def call(*args, **kwargs):
            calls.append(name)
            raise RuntimeError("provider unavailable")
        return call

    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", adapter("nvidia"))
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", adapter("ollama"))
    monkeypatch.setattr(ask_muse, "generate_interpretation", adapter("baseten"))
    with pytest.raises((ValueError, RuntimeError)):
        provider_router.generate_interpretation({}, confirmed=True)
    assert calls == ([] if selection == "unrecognized" else [selection])


@pytest.mark.parametrize("selection", ["nvidia", "baseten", "ollama"])
def test_mock_cannot_be_returned_on_live_route(monkeypatch, selection):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", selection)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-key")
    def mock(*args, **kwargs):
        return {"source": "offline_mock", "is_mock": True}
    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", mock)
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", mock)
    monkeypatch.setattr(ask_muse, "generate_interpretation", mock)
    with pytest.raises(RuntimeError):
        provider_router.generate_interpretation({}, confirmed=True)


@pytest.mark.parametrize("selection", ["nvidia", "baseten", "ollama"])
def test_agent_plan_uses_only_selected_adapter(monkeypatch, selection):
    import json
    from types import SimpleNamespace

    import agent_planner

    monkeypatch.setenv("LABLENS_AI_PROVIDER", selection)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-key")
    calls = []
    plan = {"dataset_understanding": "Measured data", "steps": [],
            "on_poor_fit": {"strategy": "halt_and_explain", "fallback_models": []},
            "stop_condition": "stop"}
    payload = json.dumps(plan)
    def hosted(config, prompt):
        calls.append("nvidia")
        return payload, "verified"
    def local(path, body=None, **kwargs):
        calls.append("ollama")
        return {"done": True, "message": {"content": payload}}
    def baseten(client, prompt, **kwargs):
        calls.append("baseten")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload))])
    monkeypatch.setattr(hosted_model_provider, "_config", lambda: {})
    monkeypatch.setattr(hosted_model_provider, "_request_content", hosted)
    monkeypatch.setattr(local_meta_provider, "check_ollama_status", lambda model: {"model_available": True})
    monkeypatch.setattr(local_meta_provider, "_request", local)
    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kwargs: object())
    monkeypatch.setattr(ask_muse, "_completion_request", baseten)
    assert agent_planner.request_agent_plan({}) == plan
    assert calls == [selection]


def test_agent_plan_requires_consent_before_any_request(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "ollama")
    monkeypatch.setattr(local_meta_provider, "_request", lambda *a, **k: pytest.fail("network attempted"))
    with pytest.raises(ValueError, match="consent"):
        provider_router.request_plan("plan", max_tokens=32)
