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
            return {"source": source, "is_mock": False,
                    "model": {"nvidia": "meta/muse-glimmer-30b", "ollama": "llama3.2:1b", "baseten": "baseten"}[name],
                    "provider": {"nvidia": "NVIDIA NIM", "ollama": local_meta_provider.SUPPORTED_MODELS["llama3.2:1b"], "baseten": "Baseten"}[name],
                    "structured": {"sections": [], "claims": []}}
        return call

    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", adapter("nvidia", "hosted_model"))
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", adapter("ollama", "local_ollama"))
    monkeypatch.setattr(ask_muse, "generate_interpretation", adapter("baseten", "live_provider"))
    report = provider_router.generate_interpretation({}, confirmed=True)
    assert calls == [selection]
    assert report["source"] == expected and report["is_mock"] is False
    assert report["model"] == {"nvidia": "meta/muse-glimmer-30b", "ollama": "llama3.2:1b", "baseten": "baseten"}[selection]


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


@pytest.mark.parametrize("selection", ["nvidia", "baseten", "ollama"])
def test_agent_interpretation_dispatch_and_evidence(monkeypatch, selection):
    import agent_planner

    monkeypatch.setenv("LABLENS_AI_PROVIDER", selection)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-key")
    calls = []
    sources = {"nvidia": "hosted_model", "baseten": "live_provider", "ollama": "local_ollama"}
    def adapter(name):
        def call(context, *args, **kwargs):
            calls.append((name, context))
            assert name == selection
            assert context["result_ids"] == ["tool.1"]
            assert context["evidence_index"]["tool.1"]["output"]["result"]["value"] == 7
            return {"model": {"nvidia": "meta/muse-glimmer-30b", "ollama": "llama3.2:1b", "baseten": "baseten"}[name],
                    "provider": {"nvidia": "NVIDIA NIM", "ollama": local_meta_provider.SUPPORTED_MODELS["llama3.2:1b"], "baseten": "Baseten"}[name],
                    "source": sources[name], "is_mock": False,
                    "structured": {"sections": [{"title": title, "content": "Review the computed result."}
                                                  for title in ask_muse.REQUIRED_TITLES], "claims": []}}
        return call
    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", adapter("nvidia"))
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", adapter("ollama"))
    monkeypatch.setattr(ask_muse, "generate_interpretation", adapter("baseten"))
    digest = {"tool_results": [{"ok": True, "tool": "fit_curve", "result": {"value": 7}}]}
    result = agent_planner.generate_grounded_interpretation(digest)
    assert len(calls) == 1 and result["source"] == sources[selection]
    assert result["is_mock"] is False and result["grounding_check"]["pass"]


def test_agent_interpretation_rejects_unknown_evidence(monkeypatch):
    import agent_planner

    monkeypatch.setenv("LABLENS_AI_PROVIDER", "nvidia")
    def fake(context, *args, **kwargs):
        report = {"sections": [{"title": title, "content": "Review the result."}
                               for title in ask_muse.REQUIRED_TITLES],
                  "claims": [{"claim": "Result", "evidence": "result", "evidence_type": "computed",
                              "confidence_or_uncertainty": "unknown", "limitation": "review needed",
                              "proposed_verification": "Repeat", "evidence_ids": ["invented.id"]}]}
        return {"model": "meta/muse-glimmer-30b", "provider": "NVIDIA NIM", "source": "hosted_model",
                "is_mock": False, "structured": report}
    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", fake)
    digest = {"tool_results": [{"ok": True, "result": {"value": 7}}]}
    assert agent_planner.generate_grounded_interpretation(digest)["rejected"] is True


def test_absent_selection_defaults_to_nvidia_and_never_baseten(monkeypatch):
    import provider_config

    monkeypatch.delenv("LABLENS_AI_PROVIDER", raising=False)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-baseten-key")
    assert provider_config.selected_ai_provider() == provider_config.get_provider() == "nvidia"
    assert provider_config.get_api_env() == "NVIDIA_API_KEY"
    assert provider_config.get_base_url() == "https://integrate.api.nvidia.com/v1"
    assert provider_config.get_model() == "meta/muse-glimmer-30b"
    assert provider_config.get_api_key() is None
    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kw: pytest.fail("Baseten called"))
    monkeypatch.setattr(local_meta_provider, "_request", lambda *a, **kw: pytest.fail("Ollama called"))
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        provider_router.generate_interpretation({}, confirmed=True)


@pytest.mark.parametrize("mode", ["nvidia", "baseten", "unknown"])
def test_direct_ollama_request_rejects_other_provider_before_network(monkeypatch, mode):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    monkeypatch.setattr(local_meta_provider.urllib.request, "build_opener", lambda *a: pytest.fail("network attempted"))
    with pytest.raises(RuntimeError, match="not the selected provider"):
        local_meta_provider._request("/api/tags")


@pytest.mark.parametrize("mode", ["nvidia", "ollama"])
def test_router_rejects_wrong_model_or_provider_provenance(monkeypatch, mode):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    wrapper = {"source": "hosted_model" if mode == "nvidia" else "local_ollama", "is_mock": False,
               "model": "wrong-model", "provider": "wrong-provider", "structured": {}}
    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", lambda *a, **kw: wrapper)
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", lambda *a, **kw: wrapper)
    with pytest.raises(RuntimeError, match="provenance"):
        provider_router.generate_interpretation({}, confirmed=True)


@pytest.mark.parametrize("mode", ["nvidia", "baseten", "ollama"])
def test_router_rejects_secret_in_context_before_adapter(monkeypatch, mode):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    monkeypatch.setenv("BASETEN_API_KEY", 'unit-secret-with-"quote')
    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", lambda *a, **kw: pytest.fail("provider called"))
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", lambda *a, **kw: pytest.fail("provider called"))
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **kw: pytest.fail("provider called"))
    with pytest.raises(ValueError, match="credential material") as error:
        provider_router.generate_interpretation({"question": 'unit-secret-with-"quote'}, confirmed=True)
    assert 'unit-secret-with-"quote' not in str(error.value)


@pytest.mark.parametrize("mode", ["nvidia", "baseten", "ollama"])
def test_router_rejects_secret_in_output(monkeypatch, mode):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    secret = "unit-fake-secret-key"
    monkeypatch.setenv("BASETEN_API_KEY", secret)
    model = {"nvidia": "meta/muse-glimmer-30b", "baseten": "muse", "ollama": "llama3.2:1b"}[mode]
    provider = {"nvidia": "NVIDIA NIM", "baseten": "Baseten", "ollama": local_meta_provider.SUPPORTED_MODELS["llama3.2:1b"]}[mode]
    source = {"nvidia": "hosted_model", "baseten": "live_provider", "ollama": "local_ollama"}[mode]
    def fake(*args, **kwargs):
        return {"model": model, "provider": provider, "source": source, "is_mock": False,
                "structured": {"sections": [{"content": secret}]}}
    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", fake)
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", fake)
    monkeypatch.setattr(ask_muse, "generate_interpretation", fake)
    with pytest.raises(RuntimeError, match="credential material") as error:
        provider_router.generate_interpretation({}, confirmed=True)
    assert secret not in str(error.value)
