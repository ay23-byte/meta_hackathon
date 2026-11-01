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
                "LABLENS_MAX_OUTPUT_TOKENS", "LABLENS_TIMEOUT_SECONDS", "BLUESMINDS_API_KEY"):
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


def configure_bluesminds(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "bluesminds")
    monkeypatch.setenv("BLUESMINDS_API_KEY", SECRET)


def test_bluesminds_success_and_request_parameters(monkeypatch):
    configure_bluesminds(monkeypatch)
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    result = hosted.generate_interpretation(CONTEXT, confirmed=True)
    init, request = calls[0][1], calls[1][1]
    assert init["base_url"] == "https://api.bluesminds.com/v1"
    assert init["api_key"] == SECRET and init["max_retries"] == 0 and init["timeout"] == 60
    assert request["model"] == "meta/muse-glimmer-30b"
    assert request["max_tokens"] == 512 and request["temperature"] == 0.2 and request["top_p"] == 1
    assert request["extra_body"] == {"reasoning_effort": "none"}
    assert result["provider"] == "Bluesminds" and SECRET not in json.dumps(result)
    monkeypatch.setenv("LABLENS_MAX_OUTPUT_TOKENS", "1024")
    monkeypatch.setenv("LABLENS_MODEL", "custom-model")
    monkeypatch.setenv("LABLENS_BASE_URL", "https://example.invalid/v1")
    hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert calls[-1][1]["max_tokens"] == 1024 and calls[-1][1]["model"] == "custom-model"
    assert calls[-2][1]["base_url"] == "https://example.invalid/v1"


def test_bluesminds_reasoning_only_is_not_content(monkeypatch):
    configure_bluesminds(monkeypatch)
    def factory(**kwargs):
        message = SimpleNamespace(content="", reasoning_content="private reasoning")
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:
            SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")]))))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    with pytest.raises(RuntimeError, match="no visible report content") as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert "private reasoning" not in str(error.value)


@pytest.mark.parametrize("key", [None, "", "your_bluesminds_api_key_here"])
def test_bluesminds_missing_key_no_request(monkeypatch, key):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "bluesminds")
    if key is not None:
        monkeypatch.setenv("BLUESMINDS_API_KEY", key)
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError, match="BLUESMINDS_API_KEY"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert not calls


@pytest.mark.parametrize("status,expected", [(401, "authentication"), (402, "payment"), (429, "rate limit"), (503, "HTTP 503")])
def test_bluesminds_http_errors(monkeypatch, status, expected):
    configure_bluesminds(monkeypatch)
    error = RuntimeError(SECRET)
    error.status_code = status
    calls = fake_client(monkeypatch, exc=error)
    with pytest.raises(RuntimeError, match=expected) as caught:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert SECRET not in str(caught.value) and len(calls) == 2


def test_bluesminds_timeout_and_malformed_response(monkeypatch):
    configure_bluesminds(monkeypatch)
    calls = fake_client(monkeypatch, exc=TimeoutError(SECRET))
    with pytest.raises(RuntimeError, match="timed out"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert len(calls) == 2
    monkeypatch.setattr(hosted, "OpenAI", lambda **kw: SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(choices={"bad": "response"})))))
    with pytest.raises(RuntimeError, match="malformed"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)


def test_bluesminds_evidence_validation(monkeypatch):
    configure_bluesminds(monkeypatch)
    candidate = report()
    candidate["claims"][0]["evidence_ids"] = ["invented.evidence"]
    fake_client(monkeypatch, content=json.dumps(candidate))
    with pytest.raises(RuntimeError, match="evidence"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    candidate = report()
    candidate["sections"][0]["content"] = "slope=999"
    fake_client(monkeypatch, content=json.dumps(candidate))
    with pytest.raises(RuntimeError, match="contradicts"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)


def test_bluesminds_connectivity_requires_consent(monkeypatch):
    configure_bluesminds(monkeypatch)
    calls = fake_client(monkeypatch, content="OK")
    with pytest.raises(ValueError, match="consent"):
        hosted.check_connectivity()
    assert not calls
    hosted.check_connectivity(confirmed=True)
    assert len(calls) == 2 and calls[-1][1]["messages"][0]["content"] == "Reply with the word OK."
    assert CONTEXT["result_ids"][0] not in json.dumps(calls[-1][1])


def test_f_interpret_routes_bluesminds_with_consent_and_preserves_provenance(monkeypatch):
    configure_bluesminds(monkeypatch)
    monkeypatch.setenv("BASETEN_API_KEY", "legacy-unit-key")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **kw: pytest.fail("legacy provider called"))
    calls = []
    captured = {}
    original = hosted.generate_interpretation

    def capture(context, titles, **kwargs):
        captured["report"] = ask_muse.generate_mock_report(context, titles, profile=kwargs["profile"])["structured"]
        return original(context, titles, **kwargs)

    def factory(**kwargs):
        calls.append(("client", kwargs))
        def create(**request):
            calls.append(("request", request))
            message = SimpleNamespace(content=json.dumps(captured["report"]), reasoning_content="hidden")
            return SimpleNamespace(model="meta/muse-glimmer-30b", choices=[SimpleNamespace(message=message, finish_reason="stop")])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(hosted, "generate_interpretation", capture)
    monkeypatch.setattr(hosted, "OpenAI", factory)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    assert not app.exception
    assert any("Bluesminds Muse Glimmer" in c.value for c in app.caption)
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not calls and any("consent" in e.value for e in app.error)
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception and not app.error
    assert len(calls) == 2 and calls[0][1]["base_url"] == "https://api.bluesminds.com/v1"
    req = calls[1][1]
    assert req["model"] == "meta/muse-glimmer-30b" and req["extra_body"] == {"reasoning_effort": "none"}
    assert req["temperature"] == 0.2 and req["top_p"] == 1 and req["max_tokens"] == 512
    assert any("Bluesminds Muse Glimmer report" in x.value for x in app.markdown)
    assert app.session_state["ai_state"]["live"]["source"] == "hosted_model"
    assert app.session_state["hosted_verification"]["generation"] is True
    # A changed model invalidates both cached report and consent.
    monkeypatch.setenv("LABLENS_MODEL", "changed-model")
    app.run()
    assert not next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).value
    assert not any("Bluesminds Muse Glimmer report" in x.value for x in app.markdown)
    assert len(calls) == 2


@pytest.mark.parametrize("case", ["402", "reasoning_only", "missing_key"])
def test_f_bluesminds_failure_no_legacy_or_mock(monkeypatch, case):
    configure_bluesminds(monkeypatch)
    monkeypatch.setenv("BASETEN_API_KEY", "legacy-unit-key")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **kw: pytest.fail("legacy provider called"))
    if case == "missing_key":
        monkeypatch.delenv("BLUESMINDS_API_KEY")
    calls = []
    def factory(**kwargs):
        calls.append(kwargs)
        def create(**request):
            if case == "402":
                err = RuntimeError(SECRET)
                err.status_code = 402
                raise err
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(
                content="", reasoning_content="private reasoning"))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception
    errors = " ".join(x.value for x in app.error)
    assert ("HTTP 402" if case == "402" else "no visible report content" if case == "reasoning_only" else "BLUESMINDS_API_KEY") in errors
    assert SECRET not in errors and "private reasoning" not in errors
    assert len(calls) == (0 if case == "missing_key" else 1)
    assert len(app.get("download_button")) == 3
    assert not any("OFFLINE MOCK report" in x.value for x in app.markdown)


def test_f_unknown_provider_never_falls_back(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "unknown")
    monkeypatch.setenv("BASETEN_API_KEY", "legacy-unit-key")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **kw: pytest.fail("legacy provider called"))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception and any("Unsupported LABLENS_AI_PROVIDER" in x.value for x in app.error)


def test_f_rejects_mismatched_provider_provenance(monkeypatch):
    configure_bluesminds(monkeypatch)
    def mismatched(context, titles, *, profile, confirmed):
        wrapper = ask_muse.generate_mock_report(context, titles, profile=profile)
        wrapper.update(source="hosted_model", provider="other-provider", model=hosted.BLUESMINDS_MODEL, is_mock=False)
        return wrapper
    monkeypatch.setattr(hosted, "generate_interpretation", mismatched)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception and any("mismatched provenance" in e.value for e in app.error)
    assert not app.session_state.get("hosted_verification", {}).get("generation")


def test_hosted_status_separates_model_and_key_without_connection(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "bluesminds")
    status = hosted.configuration_status()
    assert status["model"] == "meta/muse-glimmer-30b"
    assert status["model_configured"] and not status["api_key_detected"] and not status["live_verified"]
    monkeypatch.setenv("BLUESMINDS_API_KEY", SECRET)
    status = hosted.configuration_status()
    assert status["api_key_detected"] and status["model_configured"] and not status["live_verified"]
    assert SECRET not in json.dumps(status)


def test_connectivity_status_is_session_and_configuration_bound(monkeypatch):
    configure_bluesminds(monkeypatch)
    calls = fake_client(monkeypatch, content="OK")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(c for c in app.checkbox if c.label == "Show hosted model controls").check().run()
    next(b for b in app.button if b.label == "Test hosted API connectivity").click().run()
    assert not calls and any("consent" in e.value for e in app.error)
    next(c for c in app.checkbox if c.label.startswith("I confirmed this hosted endpoint")).check().run()
    next(b for b in app.button if b.label == "Test hosted API connectivity").click().run()
    assert len(calls) == 2
    assert app.session_state["hosted_verification"]["connectivity"] is True
    assert app.session_state["hosted_verification"]["generation"] is False
    app.run()
    status = json.loads(app.sidebar.json[0].value)
    assert status["live_connectivity_verified_this_session"] and not status["generation_succeeded_this_session"]
    monkeypatch.setenv("LABLENS_MODEL", "another-model")
    app.run()
    status = json.loads(app.sidebar.json[0].value)
    assert not status["live_connectivity_verified_this_session"] and not status["generation_succeeded_this_session"]
