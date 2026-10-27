"""Muse Spark / Baseten hardening: mocked API, config isolation, rerun safety.

No test here needs a real key or network access. Live tests are opt-in via
``pytest --run-live -m live -v`` (see ``tests/conftest.py``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import analyze_dataset
import ask_muse
import provider_config

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_voltage_current.csv"
GENERAL_APP = ROOT / "general_app.py"
FAKE_KEY = "sk-unit-test-key-ABCDEF123456"
FILE_KEY = "sk-file-fake-key-654321"
SECRET_IN_ERROR = "sk-SECRET-SHOULD-NOT-LEAK-999"


class HttpError(Exception):
    def __init__(self, status_code, *, body=None, message=None):
        super().__init__(f"provider returned {status_code}")
        self.status_code = status_code
        self.body = body
        self.message = message


class APITimeoutError(Exception):
    pass


class FakeCompletions:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        self.client.calls.append(kwargs)
        outcome = self.client.outcomes[min(len(self.client.calls) - 1,
                                           len(self.client.outcomes) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes, init_kwargs):
        self.outcomes = list(outcomes)
        self.init_kwargs = init_kwargs
        self.calls = []
        self.chat = SimpleNamespace(completions=FakeCompletions(self))


def response(content, *, finish_reason="stop", choices=True, message=True):
    msg = SimpleNamespace(content=content, model_extra={}) if message else None
    return SimpleNamespace(
        model="meta-models/muse-spark-open",
        choices=[SimpleNamespace(message=msg, finish_reason=finish_reason)] if choices else [],
    )


def valid_report():
    return {
        "sections": [
            {"title": title, "content": f"Computed evidence note {index}."}
            for index, title in enumerate(ask_muse.REQUIRED_TITLES)
        ],
        "claims": [],
    }


def valid_wrapper():
    return {"model": "meta-models/muse-spark-open", "source": "live_provider",
            "is_mock": False, "structured": valid_report()}


@pytest.fixture
def fake_provider(monkeypatch):
    created = []

    def install(outcomes, *, key=FAKE_KEY):
        if key is None:
            monkeypatch.delenv("BASETEN_API_KEY", raising=False)
        else:
            monkeypatch.setenv("BASETEN_API_KEY", key)
        monkeypatch.setattr(ask_muse, "TRANSIENT_BACKOFF_SECONDS", 0)

        def factory(**kwargs):
            client = FakeClient(outcomes, kwargs)
            created.append(client)
            return client

        monkeypatch.setattr(ask_muse, "OpenAI", factory)
        return created

    return install


def run_general_app(**kwargs):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(GENERAL_APP), default_timeout=180, **kwargs).run()


# ---------------------------------------------------------------------------
# Configuration isolation (root cause of the six historical failures)
# ---------------------------------------------------------------------------

def test_reading_dotenv_does_not_mutate_os_environ(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(f"BASETEN_API_KEY={FILE_KEY}\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "ENV_FILE", env_file)
    provider_config.reload_dotenv()
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
    try:
        assert provider_config.get_api_key() == FILE_KEY
        # Critical: dotenv_values is read, not loaded into os.environ.
        assert os.getenv("BASETEN_API_KEY") is None
    finally:
        provider_config.reload_dotenv()


def test_process_env_wins_and_disable_flag_blocks_local_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(f"BASETEN_API_KEY={FILE_KEY}\n", encoding="utf-8")
    monkeypatch.setattr(provider_config, "ENV_FILE", env_file)
    provider_config.reload_dotenv()
    monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
    try:
        monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
        assert provider_config.get_api_key() == FAKE_KEY
        assert provider_config.setting_source("BASETEN_API_KEY") == "process environment"

        monkeypatch.delenv("BASETEN_API_KEY")
        assert provider_config.get_api_key() == FILE_KEY

        monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
        assert provider_config.get_api_key() is None
        assert ask_muse.provider_status()["api_key_configured"] is False

        # Redaction covers both a process-env secret and a local .env secret,
        # even when .env fallback is disabled for configuration lookup.
        monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
        redacted = provider_config.redact(f"{FAKE_KEY} and {FILE_KEY}")
        assert FAKE_KEY not in redacted and FILE_KEY not in redacted
        assert "[redacted]" in redacted
    finally:
        provider_config.reload_dotenv()


def test_placeholder_key_is_not_configured(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "your_baseten_api_key_here")
    status = ask_muse.provider_status()
    assert status["api_key_configured"] is False
    assert status["key_state"] == "placeholder"
    assert "not configured" in status["message"]
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY is missing"):
        ask_muse.generate_interpretation({"results": {"n": 3}})


# ---------------------------------------------------------------------------
# Mocked provider contract
# ---------------------------------------------------------------------------

def test_successful_mocked_response_returns_live_wrapper(fake_provider):
    created = fake_provider([response(json.dumps(valid_report()))])
    wrapper = ask_muse.generate_interpretation({"results": {"n": 3}})
    assert wrapper["source"] == "live_provider" and wrapper["is_mock"] is False
    assert [s["title"] for s in wrapper["structured"]["sections"]] == list(
        ask_muse.REQUIRED_TITLES
    )
    client = created[-1]
    assert client.init_kwargs["base_url"] == provider_config.BASE_URL
    assert client.init_kwargs["timeout"] == ask_muse.REQUEST_TIMEOUT_SECONDS
    assert client.init_kwargs["max_retries"] == 0
    assert client.calls[0]["model"] == ask_muse.MODEL
    assert FAKE_KEY not in json.dumps(wrapper)


@pytest.mark.parametrize("key", [None, ""])
def test_missing_or_blank_key_fails_before_client(fake_provider, key):
    created = fake_provider([], key=key)
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY is missing"):
        ask_muse.generate_interpretation({"results": {"n": 3}})
    assert created == []


def test_auth_failure_is_actionable_and_not_retried(fake_provider):
    exc = HttpError(401, body={"error": {"code": "invalid_api_key",
                                         "message": SECRET_IN_ERROR}})
    created = fake_provider([exc])
    with pytest.raises(RuntimeError) as info:
        ask_muse.generate_interpretation({"results": {"n": 3}})
    message = str(info.value)
    assert "Authentication failed" in message
    assert "credential itself" in message
    assert SECRET_IN_ERROR not in message
    assert len(created[-1].calls) == 1


@pytest.mark.parametrize("code, expected", [
    ("permission_denied", "lacks permission"),
    ("model_not_found", "not available"),
    ("invalid_api_key", "credential itself"),
])
def test_403_distinguishes_permission_model_and_credential(code, expected):
    exc = HttpError(403, body={"error": {"code": code, "message": SECRET_IN_ERROR}})
    message = ask_muse.describe_provider_error(exc)
    assert "Access denied" in message and expected in message
    assert SECRET_IN_ERROR not in message
    assert "invalid key" not in message.casefold() or code == "invalid_api_key"


def test_rate_limit_is_bounded(fake_provider):
    created = fake_provider([HttpError(429)])
    with pytest.raises(RuntimeError, match="Rate limit"):
        ask_muse.generate_interpretation({"results": {"n": 3}})
    assert len(created[-1].calls) == ask_muse.MAX_TRANSIENT_RETRIES + 1 == 3


def test_timeout_is_distinguished_from_generic_network_error(fake_provider):
    created = fake_provider([APITimeoutError("slow")])
    with pytest.raises(RuntimeError, match="timed out"):
        ask_muse.generate_interpretation({"results": {"n": 3}})
    assert len(created[-1].calls) == ask_muse.MAX_TRANSIENT_RETRIES + 1
    assert "timed out" in str(ask_muse._network_error(APITimeoutError("slow")))


def test_network_failure_is_generic_and_secret_free(fake_provider):
    fake_provider([RuntimeError(f"connection failed using {SECRET_IN_ERROR}")])
    with pytest.raises(RuntimeError) as info:
        ask_muse.generate_interpretation({"results": {"n": 3}})
    assert "Could not contact" in str(info.value)
    assert SECRET_IN_ERROR not in str(info.value)


@pytest.mark.parametrize("outcome, expected", [
    (response(""), "empty content"),
    (response("   \n "), "empty content"),
    (response("not json at all"), "required JSON structure"),
    (response(json.dumps({"sections": [], "claims": []})), "required JSON structure"),
    (response(None), "empty content"),
    (response(None, choices=False), "no response choices"),
    (SimpleNamespace(model="m"), "no response choices"),
])
def test_empty_invalid_and_unexpected_responses_are_rejected(fake_provider, outcome, expected):
    fake_provider([outcome])
    with pytest.raises(RuntimeError, match=expected):
        ask_muse.generate_interpretation({"results": {"n": 3}})


def test_ai_disabled_keeps_local_analysis_and_exports(monkeypatch, tmp_path):
    def forbidden(**kwargs):
        raise AssertionError("No provider client may be created when AI is disabled.")

    monkeypatch.setattr(ask_muse, "OpenAI", forbidden)
    result = analyze_dataset.analyze_csv(SAMPLE, tmp_path, generate_ai=False)
    assert result.get("ai") is None
    assert result["fit"]["success"] is True
    for name in ("results.json", "cleaned_data.csv", "fit_parameters.csv",
                 "fit_metrics.csv", "report.md"):
        assert (tmp_path / name).is_file()
    payload = (tmp_path / "results.json").read_text(encoding="utf-8")
    assert "NaN" not in payload and "Infinity" not in payload
    assert SECRET_IN_ERROR not in payload


# ---------------------------------------------------------------------------
# Streamlit rerun / consent safety
# ---------------------------------------------------------------------------

def test_duplicate_ui_clicks_do_not_duplicate_provider_call(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []

    def fake_generate(context, section_titles=None, **kwargs):
        calls.append((context, section_titles))
        return valid_wrapper()

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_generate)
    at = run_general_app()
    at.button[0].click().run()
    at.button[0].click().run()
    assert not at.exception
    assert len(calls) == 1
    assert any("no duplicate provider request" in item.value for item in at.info)


def test_agent_requires_explicit_consent_on_every_rerun():
    at = run_general_app()
    labels = [widget.label for widget in at.checkbox]
    assert any("Run the bounded analysis agent" in label for label in labels)
    assert any("Let Muse Spark propose the plan" in label for label in labels)
    assert len({label for label in labels if "Muse Spark" in label or "agent" in label}) >= 2
    assert "Agent state" not in {metric.label for metric in at.metric}
    at.run()
    assert not at.exception
    assert "Agent state" not in {metric.label for metric in at.metric}


def test_legacy_app_duplicate_clicks_do_not_duplicate_provider_call(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []

    def fake_generate(context):
        calls.append(context)
        return valid_wrapper()

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake_generate)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    at.button[0].click().run()
    at.button[0].click().run()
    assert not at.exception
    assert len(calls) == 1
    assert any("no duplicate provider request" in item.value for item in at.info)
