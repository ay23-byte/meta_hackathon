"""Ollama provider tests use only stubs; never download a model or call a service."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ask_muse
import local_meta_provider as local
from result_schema import export_bundle

CONTEXT = {"result_ids": ["fit.linear"], "evidence_index": {"fit.linear": {"slope": 2.5}},
           "fit": {"success": True, "model": "linear", "parameters": {"slope": 2.5},
                   "metrics": {"r2": 1.0, "rmse": 0.0}, "n_observations": 12}}


def stub_report():
    return ask_muse.generate_mock_report(CONTEXT, profile="legacy")["structured"]


def test_status_and_missing_model(monkeypatch):
    monkeypatch.setattr(local, "_request", lambda *a, **k: {"models": [{"name": local.MODEL}]})
    assert local.check_ollama_status()["model_available"]
    monkeypatch.setattr(local, "_request", lambda *a, **k: {"models": [{"name": "other"}]})
    assert local.check_ollama_status()["running"] and not local.check_model_available()
    with pytest.raises(RuntimeError, match="not installed"):
        local.generate_scientific_report(CONTEXT)
    monkeypatch.setattr(local, "_request", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    assert not local.check_ollama_status()["running"]


def test_structured_response_provenance_and_export(monkeypatch):
    calls = []
    def request(path, payload=None, **kwargs):
        calls.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": local.MODEL}]}
        return {"done": True, "done_reason": "stop", "message": {"content": json.dumps(stub_report())}}
    monkeypatch.setattr(local, "_request", request)
    result = local.ask_scientific_question("What is the slope?", CONTEXT)
    assert result["source"] == "local_ollama" and result["model"] == "llama3.2:1b"
    assert calls[1][1]["options"]["temperature"] == .1 and calls[1][1]["format"] == "json"
    assert "You are Muse Spark" not in calls[1][1]["messages"][0]["content"]
    files = export_bundle({"ai": result})
    assert json.loads(files["manifest.json"])["provider"]["mode"] == "local_ollama"
    assert "Local Ollama" in files["report.md"].decode()


@pytest.mark.parametrize("reply", [
    {"model": "wrong:model", "done": True, "message": {"content": "{}"}},
    {"done": False, "message": {"content": "{}"}},
    {"done": True, "done_reason": "length", "message": {"content": "{}"}},
    {"done": True, "message": {"content": ""}},
    {"done": True, "message": {"content": "not json"}},
])
def test_invalid_local_responses_are_rejected(monkeypatch, reply):
    monkeypatch.setattr(local, "_request", lambda path, *a, **k:
                        {"models": [{"name": local.MODEL}]} if path == "/api/tags" else reply)
    with pytest.raises(RuntimeError):
        local.generate_scientific_report(CONTEXT)


def test_numeric_contradiction_is_rejected(monkeypatch):
    report = stub_report()
    report["sections"][0]["content"] = "slope=999"
    monkeypatch.setattr(local, "_request", lambda path, *a, **k:
                        {"models": [{"name": local.MODEL}]} if path == "/api/tags" else
                        {"done": True, "message": {"content": json.dumps(report)}})
    with pytest.raises(RuntimeError, match="contradicts"):
        local.generate_scientific_report(CONTEXT)


def test_network_failures_and_timeout_are_safe(monkeypatch):
    import urllib.error
    def error(exc):
        def fail(*a, **k):
            raise exc
        return fail
    class Opener:
        def __init__(self, exc):
            self.open = error(exc)
    monkeypatch.setattr(local.urllib.request, "build_opener", lambda *a: Opener(TimeoutError()))
    with pytest.raises(RuntimeError, match="timed out"):
        local._request("/api/tags")
    monkeypatch.setattr(local.urllib.request, "build_opener", lambda *a: Opener(urllib.error.URLError("offline")))
    with pytest.raises(RuntimeError, match="Cannot connect"):
        local._request("/api/tags")
    with pytest.raises(ValueError):
        local._request("/api/pull", {})


def test_ui_never_calls_ollama_until_explicit_button(monkeypatch):
    calls = []
    def fake(context, titles, profile):
        calls.append(context)
        wrapper = ask_muse.generate_mock_report(context, titles, profile=profile)
        wrapper.update(source="local_ollama", provider=local.PROVIDER, model=local.MODEL, is_mock=False)
        return wrapper
    monkeypatch.setattr(local, "generate_scientific_report", fake)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    assert not calls
    next(c for c in app.checkbox if c.label == "Enable local Ollama controls").check().run()
    assert not calls
    next(b for b in app.button if b.label == "Generate local Llama report").click().run()
    assert len(calls) == 1 and not app.exception and not app.error
    assert any("Local Llama response received" in s.value for s in app.success)
    assert any("Local Ollama" in c.value for c in app.code)
    next(w for w in app.text_input if w.label == "Ask a question about this analysis (optional)").set_value("Explain the slope").run()
    assert len(calls) == 1
    assert any("Local report is stale" in c.value for c in app.caption)


def test_transport_rejects_malformed_and_oversized_response(monkeypatch):
    class Response:
        def __init__(self, value):
            self.value = value
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return self.value
    class Opener:
        def __init__(self, value):
            self.value = value
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/tags"
            return Response(self.value)
    monkeypatch.setattr(local.urllib.request, "build_opener", lambda *args: Opener(b"invalid json"))
    with pytest.raises(RuntimeError, match="malformed JSON"):
        local._request("/api/tags")
    monkeypatch.setattr(local.urllib.request, "build_opener", lambda *args: Opener(b"x" * (local.MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(RuntimeError, match="size limit"):
        local._request("/api/tags")
