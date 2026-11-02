"""Hosted provider contract: fake clients only; no network or paid requests."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import ask_muse
import hosted_model_provider as hosted
from result_schema import export_bundle

SECRET = "unit-hosted-private-key-123456789"
TEST_MODEL = "test-catalog/example-model"


def fake_catalog():
    return SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id=os.environ.get("NVIDIA_MODEL", TEST_MODEL))]))
CONTEXT = {"result_ids": ["fit.linear"], "evidence_index": {"fit.linear": {"slope": 2.5}},
           "fit": {"success": True, "model": "linear", "parameters": {"slope": 2.5},
                   "metrics": {"r2": 1.0, "rmse": 0.0}, "n_observations": 12}}


@pytest.fixture(autouse=True)
def clear_hosted_env(monkeypatch, tmp_path):
    import provider_config

    # Tests must never read a developer's external credentials.
    monkeypatch.setattr(provider_config, "NVIDIA_ENV_FILE", tmp_path / "absent.env")
    for key in ("LABLENS_AI_PROVIDER", "LABLENS_API_KEY", "LABLENS_BASE_URL", "LABLENS_MODEL",
                "LABLENS_MAX_OUTPUT_TOKENS", "LABLENS_TIMEOUT_SECONDS", "LABLENS_NVIDIA_STREAM", "NVIDIA_API_KEY", "NVIDIA_MODEL"):
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
        return SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
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


def configure_nvidia(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", SECRET)
    monkeypatch.setenv("NVIDIA_MODEL", TEST_MODEL)


def test_nvidia_success_and_request_parameters(monkeypatch):
    configure_nvidia(monkeypatch)
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    result = hosted.generate_interpretation(CONTEXT, confirmed=True)
    init, request = calls[0][1], calls[1][1]
    assert init["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert init["api_key"] == SECRET and init["max_retries"] == 0
    assert init["timeout"].connect == 10 and init["timeout"].read == 120
    assert request["model"] == TEST_MODEL
    assert request["max_tokens"] == 512 and request["temperature"] == 0.2 and request["top_p"] == 1
    assert "extra_body" not in request
    assert result["provider"] == "NVIDIA NIM" and SECRET not in json.dumps(result)
    monkeypatch.setenv("LABLENS_MAX_OUTPUT_TOKENS", "1024")
    monkeypatch.setenv("NVIDIA_MODEL", "custom-model")
    monkeypatch.setenv("LABLENS_BASE_URL", "https://example.invalid/v1")
    hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert calls[-1][1]["max_tokens"] == 1024 and calls[-1][1]["model"] == "custom-model"
    assert calls[-2][1]["base_url"] == "https://integrate.api.nvidia.com/v1"


def test_nvidia_reasoning_only_is_not_content(monkeypatch):
    configure_nvidia(monkeypatch)
    def factory(**kwargs):
        message = SimpleNamespace(content="", reasoning_content="private reasoning")
        return SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:
            SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")]))))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    with pytest.raises(RuntimeError, match="no visible report content") as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert "private reasoning" not in str(error.value)


@pytest.mark.parametrize("key", [None, "", "your_nvidia_api_key_here"])
def test_nvidia_missing_key_no_request(monkeypatch, key):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "nvidia")
    if key is not None:
        monkeypatch.setenv("NVIDIA_API_KEY", key)
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert not calls


@pytest.mark.parametrize("status,expected", [(401, "authentication"), (403, "access"), (402, "payment"), (429, "rate limit"), (503, "HTTP 503")])
def test_nvidia_http_errors(monkeypatch, status, expected):
    configure_nvidia(monkeypatch)
    error = RuntimeError(SECRET)
    error.status_code = status
    calls = fake_client(monkeypatch, exc=error)
    with pytest.raises(RuntimeError, match=expected) as caught:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert SECRET not in str(caught.value) and len(calls) == 2


def test_nvidia_timeout_and_malformed_response(monkeypatch):
    configure_nvidia(monkeypatch)
    calls = fake_client(monkeypatch, exc=TimeoutError(SECRET))
    with pytest.raises(RuntimeError, match="timed out"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert len(calls) == 2
    monkeypatch.setattr(hosted, "OpenAI", lambda **kw: SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(
        completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(choices={"bad": "response"})))))
    with pytest.raises(RuntimeError, match="malformed"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)


def test_nvidia_evidence_validation(monkeypatch):
    configure_nvidia(monkeypatch)
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


def test_nvidia_connectivity_requires_consent(monkeypatch):
    configure_nvidia(monkeypatch)
    calls = fake_client(monkeypatch, content="OK")
    with pytest.raises(ValueError, match="consent"):
        hosted.check_connectivity()
    assert not calls
    hosted.check_connectivity(confirmed=True)
    assert len(calls) == 2 and calls[-1][1]["messages"][0]["content"] == "Reply with the word OK."
    assert CONTEXT["result_ids"][0] not in json.dumps(calls[-1][1])


def test_f_interpret_routes_nvidia_with_consent_and_preserves_provenance(monkeypatch):
    configure_nvidia(monkeypatch)
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
            return SimpleNamespace(model=TEST_MODEL, choices=[SimpleNamespace(message=message, finish_reason="stop")])
        return SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(hosted, "generate_interpretation", capture)
    monkeypatch.setattr(hosted, "OpenAI", factory)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    assert not app.exception
    assert any("NVIDIA NIM" in c.value for c in app.caption)
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not calls and any("consent" in e.value for e in app.error)
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception and not app.error
    assert len(calls) == 2 and calls[0][1]["base_url"] == "https://integrate.api.nvidia.com/v1"
    req = calls[1][1]
    assert req["model"] == TEST_MODEL and "extra_body" not in req
    assert req["temperature"] == 0.2 and req["top_p"] == 1 and req["max_tokens"] == 512
    assert any("NVIDIA NIM report" in x.value for x in app.markdown)
    assert app.session_state["ai_state"]["live"]["source"] == "hosted_model"
    assert app.session_state["hosted_verification"]["generation"] is True
    # A changed model invalidates both cached report and consent.
    monkeypatch.setenv("NVIDIA_MODEL", "changed-model")
    app.run()
    assert not next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).value
    assert not any("NVIDIA NIM report" in x.value for x in app.markdown)
    assert len(calls) == 2


@pytest.mark.parametrize("case", ["402", "reasoning_only", "missing_key"])
def test_f_nvidia_failure_no_legacy_or_mock(monkeypatch, case):
    configure_nvidia(monkeypatch)
    monkeypatch.setenv("BASETEN_API_KEY", "legacy-unit-key")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **kw: pytest.fail("legacy provider called"))
    if case == "missing_key":
        monkeypatch.delenv("NVIDIA_API_KEY")
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
        return SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception
    errors = " ".join(x.value for x in app.error)
    assert ("HTTP 402" if case == "402" else "no visible report content" if case == "reasoning_only" else "NVIDIA_API_KEY") in errors
    assert "NVIDIA NIM request failed" in errors and "Muse Spark request failed" not in errors
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
    configure_nvidia(monkeypatch)
    def mismatched(context, titles, *, profile, confirmed):
        wrapper = ask_muse.generate_mock_report(context, titles, profile=profile)
        wrapper.update(source="hosted_model", provider="other-provider", model=TEST_MODEL, is_mock=False)
        return wrapper
    monkeypatch.setattr(hosted, "generate_interpretation", mismatched)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception and any("mismatched provenance" in e.value for e in app.error)
    assert not app.session_state.get("hosted_verification", {}).get("generation")


def test_hosted_status_separates_model_and_key_without_connection(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_MODEL", TEST_MODEL)
    status = hosted.configuration_status()
    assert status["model"] == TEST_MODEL
    assert status["model_configured"] and not status["api_key_detected"] and not status["live_verified"]
    monkeypatch.setenv("NVIDIA_API_KEY", SECRET)
    status = hosted.configuration_status()
    assert status["api_key_detected"] and status["model_configured"] and not status["live_verified"]
    assert SECRET not in json.dumps(status)


def test_connectivity_status_is_session_and_configuration_bound(monkeypatch):
    configure_nvidia(monkeypatch)
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
    monkeypatch.setenv("NVIDIA_MODEL", "another-model")
    app.run()
    status = json.loads(app.sidebar.json[0].value)
    assert not status["live_connectivity_verified_this_session"] and not status["generation_succeeded_this_session"]


def test_nvidia_requires_explicit_model_and_never_uses_legacy_override(monkeypatch):
    configure_nvidia(monkeypatch)
    monkeypatch.delenv("NVIDIA_MODEL")
    monkeypatch.setenv("LABLENS_MODEL", "legacy-unrelated-model")
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError, match="NVIDIA_MODEL"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert not calls


def test_bluesminds_mode_is_disabled_without_fallback(monkeypatch):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "bluesminds")
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError, match="hosted or nvidia"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert not calls


def test_nvidia_parent_env_precedence_redaction_and_rotation(monkeypatch, tmp_path):
    import provider_config

    env_file = tmp_path / "meta-hacathon.env"
    env_file.write_text(f"NVIDIA_API_KEY={SECRET}\nNVIDIA_MODEL={TEST_MODEL}\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "NVIDIA_ENV_FILE", env_file)
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "nvidia")
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    # fake_catalog reads process env; test the adapter with a custom catalog below.
    monkeypatch.setenv("NVIDIA_MODEL", TEST_MODEL)
    first = hosted.configuration_fingerprint()
    assert hosted.configuration_status()["api_key_detected"]
    assert SECRET not in json.dumps(hosted.configuration_status())
    assert SECRET not in provider_config.redact(f"error {SECRET}")
    hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert calls[0][1]["api_key"] == SECRET
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    with pytest.raises(ValueError, match="NVIDIA_API_KEY"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    monkeypatch.setenv("NVIDIA_API_KEY", "second-private-key-123")
    assert hosted.configuration_fingerprint() != first
    monkeypatch.delenv("NVIDIA_MODEL")
    assert provider_config.nvidia_setting("NVIDIA_MODEL") == TEST_MODEL
    env_file.write_text("NVIDIA_MODEL=changed-catalog-model\n", encoding="utf-8")
    assert provider_config.nvidia_setting("NVIDIA_MODEL") == "changed-catalog-model"
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    assert not provider_config.nvidia_setting("NVIDIA_MODEL")


@pytest.mark.parametrize("catalog_case", ["missing", "malformed", "paginated", "unsupported", "server"])
def test_nvidia_catalog_validation_before_inference(monkeypatch, catalog_case):
    configure_nvidia(monkeypatch)
    calls = []
    def list_models():
        calls.append("catalog")
        if catalog_case in ("unsupported", "server"):
            exc = RuntimeError(SECRET)
            exc.status_code = 404 if catalog_case == "unsupported" else 503
            raise exc
        if catalog_case == "malformed":
            return SimpleNamespace(data="bad")
        return SimpleNamespace(data=[SimpleNamespace(id="different-model")], has_more=catalog_case == "paginated")
    def create(**kwargs):
        calls.append("inference")
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(report())))])
    monkeypatch.setattr(hosted, "OpenAI", lambda **kw: SimpleNamespace(
        models=SimpleNamespace(list=list_models), chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    if catalog_case == "unsupported":
        result = hosted.generate_interpretation(CONTEXT, confirmed=True)
        assert result["model_catalog_status"] == "unavailable_or_unsupported"
        assert calls == ["catalog", "inference"]
    else:
        with pytest.raises(RuntimeError) as error:
            hosted.generate_interpretation(CONTEXT, confirmed=True)
        assert SECRET not in str(error.value)
        assert calls == ["catalog"]
        if catalog_case == "server":
            assert "HTTP 503" in str(error.value)


def test_nvidia_sdk_uses_chat_completions_endpoint_offline(monkeypatch):
    """Exercise the SDK wire format with a mock transport, never a network call."""
    import openai._base_client as base_client

    http = getattr(base_client, "httpx2", None) or base_client.httpx
    configure_nvidia(monkeypatch)
    requests = []
    def handle(request):
        requests.append(request)
        if request.url.path == "/v1/models":
            return http.Response(200, json={"object": "list", "data": [{"id": TEST_MODEL, "object": "model"}]})
        if request.url.path == "/v1/chat/completions":
            return http.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
                "model": TEST_MODEL, "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(report())}}]})
        raise AssertionError("Unexpected endpoint")
    transport = http.MockTransport(handle)
    client = http.Client(transport=transport)
    original = hosted.OpenAI
    monkeypatch.setattr(hosted, "OpenAI", lambda **kw: original(http_client=client, **kw))
    result = hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert result["model_catalog_status"] == "verified"
    assert [(r.method, r.url.path) for r in requests] == [("GET", "/v1/models"), ("POST", "/v1/chat/completions")]
    assert all(str(r.url).startswith("https://integrate.api.nvidia.com/") for r in requests)
    body = json.loads(requests[1].content)
    assert body["model"] == TEST_MODEL and body["max_tokens"] == 512
    assert body["temperature"] == 0.2 and body["top_p"] == 1
    assert SECRET not in json.dumps(result)
    client.close()


def _chunk(content=None, *, reason=None, model=TEST_MODEL, reasoning=None, refusal=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning, refusal=refusal)
    return SimpleNamespace(model=model, choices=[SimpleNamespace(index=0, delta=delta, finish_reason=reason)])


def _stream_client(monkeypatch, chunks):
    calls = []
    def factory(**kwargs):
        def create(**request):
            calls.append(request)
            return iter(chunks)
        return SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(hosted, "OpenAI", factory)
    return calls


def test_nvidia_stream_buffers_content_and_validates(monkeypatch):
    configure_nvidia(monkeypatch)
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "1")
    raw = json.dumps(report())
    calls = _stream_client(monkeypatch, [_chunk(None, reasoning="never display"), _chunk(raw[:30]),
                                       _chunk(raw[30:], reason="stop", reasoning="private")])
    result = hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert calls[0]["stream"] is True and calls[0]["model"] == TEST_MODEL
    assert result["structured"] == report() and "private" not in json.dumps(result)
    assert result["source"] == "hosted_model" and result["model_catalog_status"] == "verified"


@pytest.mark.parametrize("chunks, expected", [
    ([_chunk(reasoning="secret reasoning", reason="stop")], "no visible"),
    ([_chunk("incomplete")], "without a final completion"),
    ([_chunk("partial", reason="length")], "truncated"),
    ([_chunk("some", model="different", reason="stop")], "different model"),
    ([_chunk(refusal="private refusal", reason="stop")], "declined"),
    ([_chunk("{}", reason="stop")], "schema"),
])
def test_nvidia_stream_rejects_invalid_without_reasoning_leak(monkeypatch, chunks, expected):
    configure_nvidia(monkeypatch)
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "1")
    _stream_client(monkeypatch, chunks)
    with pytest.raises(RuntimeError, match=expected) as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert "secret reasoning" not in str(error.value) and "private refusal" not in str(error.value)


def test_nvidia_stream_iteration_failure_does_not_return_partial(monkeypatch):
    configure_nvidia(monkeypatch)
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "1")
    def chunks():
        yield _chunk("partial response")
        raise TimeoutError(SECRET)
    _stream_client(monkeypatch, chunks())
    with pytest.raises(RuntimeError, match="timed out") as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert SECRET not in str(error.value) and "partial response" not in str(error.value)


def test_nvidia_stream_setting_is_validated_and_fingerprint_bound(monkeypatch):
    configure_nvidia(monkeypatch)
    previous = hosted.configuration_fingerprint()
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "1")
    assert hosted.configuration_fingerprint() != previous
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "true")
    calls = fake_client(monkeypatch)
    with pytest.raises(ValueError, match="LABLENS_NVIDIA_STREAM"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert not calls


def test_nvidia_stream_rejects_invalid_evidence(monkeypatch):
    configure_nvidia(monkeypatch)
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "1")
    candidate = report()
    candidate["claims"][0]["evidence_ids"] = ["invented.evidence"]
    _stream_client(monkeypatch, [_chunk(json.dumps(candidate), reason="stop")])
    with pytest.raises(RuntimeError, match="evidence"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)


@pytest.mark.parametrize("stream", ["0", "1"])
def test_parent_env_selects_nvidia_for_f_interpret(monkeypatch, tmp_path, stream):
    import provider_config

    model = "meta/muse-glimmer-30b"
    env_file = tmp_path / ".env"
    env_file.write_text(f"LABLENS_AI_PROVIDER=nvidia\nNVIDIA_API_KEY={SECRET}\nNVIDIA_MODEL={model}\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "NVIDIA_ENV_FILE", env_file)
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", stream)
    monkeypatch.setenv("BASETEN_API_KEY", "legacy-private-unit-key")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **kw: pytest.fail("Baseten was called"))
    calls = []
    captured = {}
    original = hosted.generate_interpretation
    def capture(context, titles, **kwargs):
        captured["response"] = json.dumps(ask_muse.generate_mock_report(context, titles, profile=kwargs["profile"])["structured"])
        return original(context, titles, **kwargs)
    def client_factory(**kwargs):
        calls.append(("client", kwargs))
        def create(**request):
            calls.append(("request", request))
            if stream == "1":
                content = captured["response"]
                return iter([_chunk(reasoning="hidden", model=model), _chunk(content[:50], model=model),
                             _chunk(content[50:], model=model, reason="stop")])
            return SimpleNamespace(model=model, choices=[SimpleNamespace(finish_reason="stop",
                message=SimpleNamespace(content=captured["response"], reasoning_content="hidden"))])
        return SimpleNamespace(models=SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id=model)])),
                               chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(hosted, "generate_interpretation", capture)
    monkeypatch.setattr(hosted, "OpenAI", client_factory)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    assert not app.exception and any("NVIDIA NIM" in item.value and model in item.value for item in app.caption)
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not calls and any("consent" in item.value for item in app.error)
    next(c for c in app.checkbox if c.label.startswith("I confirmed the hosted endpoint and charges and consent to send this analysis from F")).check().run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert not app.exception and not app.error and len(calls) == 2
    assert calls[0][1]["api_key"] == SECRET and calls[0][1]["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert calls[0][1]["max_retries"] == 0 and calls[1][1]["model"] == model
    assert calls[1][1]["stream"] == (stream == "1")
    assert app.session_state["ai_state"]["live"]["provider"] == "NVIDIA NIM"
    assert SECRET not in " ".join(e.value for e in app.error)


def test_provider_selection_process_precedence_and_file_fingerprint(monkeypatch, tmp_path):
    import provider_config

    env_file = tmp_path / ".env"
    env_file.write_text(f"LABLENS_AI_PROVIDER=nvidia\nNVIDIA_API_KEY={SECRET}\nNVIDIA_MODEL=meta/muse-glimmer-30b\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "NVIDIA_ENV_FILE", env_file)
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
    assert provider_config.selected_ai_provider() == "nvidia"
    fingerprint = hosted.configuration_fingerprint()
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "unsupported-provider")
    assert provider_config.selected_ai_provider() == "unsupported-provider"
    assert hosted.configuration_fingerprint() != fingerprint
    with pytest.raises(ValueError, match="hosted or nvidia"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    monkeypatch.setenv("LABLENS_AI_PROVIDER", "")
    assert provider_config.selected_ai_provider() == "invalid-empty-provider"
    with pytest.raises(ValueError, match="hosted or nvidia"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    monkeypatch.delenv("LABLENS_AI_PROVIDER")
    env_file.write_text("LABLENS_AI_PROVIDER=unknown\n", encoding="utf-8")
    assert provider_config.selected_ai_provider() == "unknown"
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    assert provider_config.selected_ai_provider() == ""


def test_provider_change_clears_stale_error_without_call(monkeypatch, tmp_path):
    import provider_config

    env_file = tmp_path / ".env"
    env_file.write_text("LABLENS_AI_PROVIDER=nvidia\nNVIDIA_MODEL=meta/muse-glimmer-30b\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "NVIDIA_ENV_FILE", env_file)
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(b for b in app.button if b.label == "Generate evidence-grounded interpretation").click().run()
    assert app.session_state["ai_last_error"]
    env_file.write_text("LABLENS_AI_PROVIDER=unknown\n", encoding="utf-8")
    app.run()
    assert not app.session_state.get("ai_last_error") and not app.exception
    assert any("Unsupported LABLENS_AI_PROVIDER" in e.value for e in app.error)


def test_nvidia_project_dotenv_and_process_precedence(monkeypatch, tmp_path):
    import provider_config

    project = tmp_path / "project" / ".env"
    project.parent.mkdir()
    legacy = tmp_path / "legacy.env"
    project.write_text("LABLENS_AI_PROVIDER=nvidia\nNVIDIA_API_KEY=unit-project-secret\n"
                       "NVIDIA_MODEL=meta/muse-glimmer-30b\n", encoding="utf-8")
    legacy.write_text("NVIDIA_API_KEY=unit-legacy-secret\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "ROOT", project.parent)
    monkeypatch.setattr(provider_config, "NVIDIA_ENV_FILE", project)
    monkeypatch.setattr(provider_config, "NVIDIA_LEGACY_ENV_FILE", legacy)
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV")
    assert provider_config.selected_ai_provider() == "nvidia"
    assert provider_config.nvidia_setting("NVIDIA_API_KEY") == "unit-project-secret"
    assert "NVIDIA_API_KEY" not in os.environ
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    assert provider_config.nvidia_setting("NVIDIA_API_KEY") == ""
    monkeypatch.delenv("NVIDIA_API_KEY")
    project.unlink()
    assert provider_config.nvidia_setting("NVIDIA_API_KEY") == "unit-legacy-secret"
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    assert provider_config.nvidia_setting("NVIDIA_API_KEY") == ""


@pytest.mark.parametrize("exception_type, expected", [
    (hosted.httpx.ConnectTimeout, "connection"),
    (hosted.httpx.ReadTimeout, "read"),
    (hosted.httpx.WriteTimeout, "write"),
])
def test_timeout_categories_and_safe_diagnostics(monkeypatch, caplog, exception_type, expected):
    import logging

    configure_nvidia(monkeypatch)
    calls = fake_client(monkeypatch, exc=exception_type(SECRET))
    with caplog.at_level(logging.INFO, logger=hosted.__name__):
        with pytest.raises(RuntimeError, match=expected) as error:
            hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert len(calls) == 2
    assert SECRET not in str(error.value) and SECRET not in caplog.text
    assert f"timeout_category={expected}" in caplog.text
    assert "attempt=1" in caplog.text and "completion=failed" in caplog.text


def test_timeout_configuration_and_fingerprint(monkeypatch):
    configure_nvidia(monkeypatch)
    old = hosted.configuration_fingerprint()
    monkeypatch.setenv("LABLENS_CONNECT_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("LABLENS_READ_TIMEOUT_SECONDS", "240")
    calls = fake_client(monkeypatch, content=json.dumps(report()))
    hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert calls[0][1]["timeout"].connect == 7
    assert calls[0][1]["timeout"].read == 240
    assert old != hosted.configuration_fingerprint()
    monkeypatch.setenv("LABLENS_READ_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError, match="LABLENS_READ_TIMEOUT_SECONDS"):
        hosted.generate_interpretation(CONTEXT, confirmed=True)


def test_stream_read_timeout_closes_and_does_not_retry(monkeypatch):
    configure_nvidia(monkeypatch)
    monkeypatch.setenv("LABLENS_NVIDIA_STREAM", "1")
    closed = []
    calls = []

    class PartialStream:
        def __iter__(self):
            yield _chunk("sensitive partial")
            raise hosted.httpx.ReadTimeout(SECRET)

        def close(self):
            closed.append(True)

    def factory(**kwargs):
        def create(**request):
            calls.append(request)
            return PartialStream()
        return SimpleNamespace(models=fake_catalog(), chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(hosted, "OpenAI", factory)
    with pytest.raises(RuntimeError, match="stream inactivity or read") as error:
        hosted.generate_interpretation(CONTEXT, confirmed=True)
    assert len(calls) == 1 and closed == [True]
    assert SECRET not in str(error.value) and "sensitive partial" not in str(error.value)
