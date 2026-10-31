"""Hosted provider contract: fake clients only; no network or paid requests."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import ask_muse
import hosted_model_provider as hosted
from result_schema import export_bundle

SECRET = "unit-hosted-private-key-123456789"
CONTEXT = {"result_ids": ["fit.linear"], "evidence_index": {"fit.linear": {"slope": 2.5}},
           "fit": {"success": True, "model": "linear", "parameters": {"slope": 2.5},
                   "metrics": {"r2": 1.0, "rmse": 0.0}, "n_observations": 12}}


@pytest.fixture(autouse=True)
def clear_hosted_env(monkeypatch):
    for key in ("LABLENS_AI_PROVIDER", "LABLENS_API_KEY", "LABLENS_BASE_URL", "LABLENS_MODEL",
                "LABLENS_MAX_OUTPUT_TOKENS", "LABLENS_TIMEOUT_SECONDS"):
        monkeypatch.delenv(key, raising=False)


def configured(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "hosted")
    monkeypatch.setenv("LABLENS_API_KEY", SECRET)
    monkeypatch.setenv("LABLENS_BASE_URL", "https://example.invalid/v1")


def report():
    return ask_muse.generate_mock_report(CONTEXT, profile="legacy")["structured"]


def fake_client(monkeypatch, *, content=None, exc=None):
    calls = []
    def factory(**kwargs):
        calls.append(("init", kwargs))
        def create(**request):
            calls.append(("request", request))
            if exc:
                raise exc
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    return calls


@pytest.mark.parametrize("missing", ["LABLENS_AI_PROVIDER", "LABLENS_API_KEY", "LABLENS_BASE_URL", "LABLENS_MODEL"])
def test_missing_config_and_unconsented_make_no_client(monkeypatch, missing):
    configured(monkeypatch)
    monkeypatch.setenv(missing, "")
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert calls == []
    with pytest.raises(ValueError, match="consent"):
        hosted.generate_interpretation(CONTEXT, confirmed=False)
    assert calls == []


@pytest.mark.parametrize("url", ["http://example.invalid", "https://key:pass@example.invalid", "https://example.invalid/?key=secret"])
def test_url_must_be_https_and_without_url_credentials(monkeypatch, url):
    configured(monkeypatch)
    monkeypatch.setenv("LABLENS_BASE_URL", url)
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert not calls


def test_mock_success_once_and_export_provenance(monkeypatch):
    configured(monkeypatch)
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    result = hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert len(calls) == 2 and calls[0][1]["max_retries"] == 0
    assert calls[1][1]["model"] == hosted.DEFAULT_MODEL
    assert result["model"] == hosted.DEFAULT_MODEL and result["source"] == "hosted_model"
    assert SECRET not in json.dumps(result) and not hosted.configuration_status()["live_verified"]
    files = export_bundle({"ai": result})
    assert json.loads(files["manifest.json"])["provider"]["mode"] == "hosted"
    assert SECRET not in files["report.md"].decode()


@pytest.mark.parametrize("kind", ["empty", "malformed", "unknown_id", "slope", "secret"])
def test_invalid_responses_rejected_without_fallback(monkeypatch, kind):
    configured(monkeypatch)
    output = report()
    if kind == "unknown_id":
        output["claims"][0]["evidence_ids"] = ["previous-analysis"]
    if kind == "slope":
        output["sections"][0]["content"] = "slope=999"
    content = "" if kind == "empty" else "broken" if kind == "malformed" else SECRET if kind == "secret" else json.dumps(output)
    calls = fake_client(monkeypatch, content=content)
    with pytest.raises(RuntimeError) as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert SECRET not in str(error.value) and len(calls) == 2


@pytest.mark.parametrize("status,expected", [(401, "authentication"), (403, "access"), (429, "rate limit"), (500, "HTTP 500")])
def test_provider_errors_are_safe_and_never_retried(monkeypatch, status, expected):
    configured(monkeypatch)
    error = RuntimeError(SECRET)
    error.status_code = status
    calls = fake_client(monkeypatch, exc=error)
    with pytest.raises(RuntimeError, match=expected) as caught:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert SECRET not in str(caught.value) and len(calls) == 2


def test_timeout_sanitized_and_config_change_invalidates_fingerprint(monkeypatch):
    configured(monkeypatch)
    before = hosted.configuration_fingerprint()
    monkeypatch.setenv("LABLENS_MODEL", "official-model-override")
    assert before != hosted.configuration_fingerprint()
    calls = fake_client(monkeypatch, exc=TimeoutError(SECRET))
    with pytest.raises(RuntimeError, match="timed out") as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert SECRET not in str(error.value) and len(calls) == 2


def test_ui_explicit_consent_and_stale_analysis(monkeypatch):
    configured(monkeypatch)
    calls = []
    def fake(context, titles, *, profile, confirmed):
        assert confirmed is True
        calls.append(context)
        wrapper = ask_muse.generate_mock_report(context, titles, profile=profile)
        wrapper.update(source="hosted_model", provider=hosted.PROVIDER_NAME, model=hosted.DEFAULT_MODEL, is_mock=False)
        return wrapper
    monkeypatch.setattr(hosted, "generate_interpretation", fake)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    assert not calls
    next(c for c in app.checkbox if c.label == "Show hosted model controls").check().run()
    assert not calls
    # Do not bypass consent by clicking the action; real adapter rejects before client creation.
    next(c for c in app.checkbox if c.label.startswith("I confirmed this hosted endpoint")).check().run()
    assert not calls
    next(b for b in app.button if b.label == "Generate hosted model interpretation").click().run()
    assert len(calls) == 1 and not app.exception and not app.error
    assert any("Hosted response received" in item.value for item in app.success)
    next(w for w in app.text_input if w.label == "X unit (optional)").set_value("changed").run()
    assert len(calls) == 1
    assert not any("Hosted response received" in item.value for item in app.success)
    assert not next(c for c in app.checkbox if c.label.startswith("I confirmed this hosted endpoint")).value


def test_ui_does_not_construct_client_without_consent(monkeypatch):
    configured(monkeypatch)
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(c for c in app.checkbox if c.label == "Show hosted model controls").check().run()
    next(b for b in app.button if b.label == "Generate hosted model interpretation").click().run()
    assert not calls and not app.exception
    assert any("consent" in error.value for error in app.error)
    assert len(app.get("download_button")) == 3


def test_mismatched_evidence_registry_and_model_are_rejected(monkeypatch):
    configured(monkeypatch)
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    invalid = {**CONTEXT, "evidence_index": {"other": {}}}
    with pytest.raises(ValueError, match="registry"):
        hosted.generate_interpretation(invalid, confirmed=True)
    assert not calls
    def factory(**kwargs):
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **request:
            SimpleNamespace(model="other-model", choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(report())))]))))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    with pytest.raises(RuntimeError, match="different model"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)


def test_secret_in_context_is_rejected_without_request(monkeypatch):
    configured(monkeypatch)
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    with pytest.raises(ValueError, match="credential material") as error:
        hosted.generate_interpretation({**CONTEXT, "research_question": SECRET}, confirmed=True)
    assert SECRET not in str(error.value) and not calls


def test_semantic_support_is_explicitly_unverified(monkeypatch):
    configured(monkeypatch)
    candidate = report()
    candidate["claims"][0]["claim"] = "The experiment proves a physical mechanism."
    fake_client(monkeypatch, content=json.dumps(candidate))
    result = hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert result["numeric_guard"]["status"] == "partially_checked"
    assert result["numeric_guard"]["unverified"]
    assert "semantic evidence support are not verified" in result["numeric_guard"]["limitations"]
