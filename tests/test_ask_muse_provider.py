"""Offline contract tests for the Muse Spark/Baseten adapter.

These use a fake OpenAI-compatible client. They verify the request we send,
the way we parse and validate responses, error mapping, and the secret-free
fallback path. They do NOT verify that the live provider is reachable; use
``test_muse.py`` with a real BASETEN_API_KEY for that.
"""

import json
from types import SimpleNamespace

import pytest

import ask_muse

SECRET = "sk-unit-test-DO-NOT-LEAK-90210"


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider returned {status_code}")
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        self.client.calls.append(kwargs)
        index = min(len(self.client.calls) - 1, len(self.client.outcomes) - 1)
        outcome = self.client.outcomes[index]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes, init_kwargs):
        self.outcomes = outcomes
        self.init_kwargs = init_kwargs
        self.calls = []
        self.chat = SimpleNamespace(completions=FakeCompletions(self))


@pytest.fixture
def fake_provider(monkeypatch):
    """Install a fake OpenAI client and return the recorded state."""
    monkeypatch.setenv("BASETEN_API_KEY", SECRET)
    created = []

    def install(outcomes):
        def factory(**kwargs):
            client = FakeClient(list(outcomes), kwargs)
            created.append(client)
            return client

        monkeypatch.setattr(ask_muse, "OpenAI", factory)
        return created

    return install


def make_response(
    content,
    *,
    finish_reason="stop",
    model="meta-models/muse-spark-open",
    message_extra=None,
    with_message=True,
    choices=True,
):
    message = (
        SimpleNamespace(content=content, model_extra=message_extra or {})
        if with_message
        else None
    )
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)]
        if choices
        else [],
    )


def valid_report(*, extra_keys=False, section_titles=None):
    titles = section_titles or list(ask_muse.REQUIRED_TITLES)
    report = {
        "sections": [
            {"title": title, "content": f"Concise evidence note {index}."}
            for index, title in enumerate(titles)
        ],
        "claims": [
            {
                "claim": "The fitted slope is positive.",
                "evidence": "Computed OLS slope from the supplied context.",
                "evidence_type": "computed_result",
                "confidence_or_uncertainty": "No calibration uncertainty available.",
                "limitation": "Only eleven paired measurements.",
                "proposed_verification": "Repeat at additional currents.",
            }
        ],
    }
    if extra_keys:
        report["unexpected_top_level"] = "must not reach exports"
        report["sections"][0]["unexpected_field"] = "must not reach exports"
        report["claims"][0]["unexpected_field"] = "must not reach exports"
    return report


def as_content(report, fenced=False):
    text = json.dumps(report)
    return f"```json\n{text}\n```" if fenced else text


CONTEXT = {"results": {"slope": 4.99, "n": 11}, "model": "V = mI + b"}


def test_valid_response_uses_documented_request_and_sanitizes_output(fake_provider):
    created = fake_provider(
        [make_response(as_content(valid_report(extra_keys=True)))]
    )

    result = ask_muse.generate_interpretation(CONTEXT)

    client = created[0]
    assert client.init_kwargs["base_url"] == "https://inference.baseten.co/v1"
    assert client.init_kwargs["timeout"] == ask_muse.REQUEST_TIMEOUT_SECONDS
    assert client.init_kwargs["max_retries"] == 0  # local bounded retries own the policy
    assert client.init_kwargs["api_key"] == SECRET

    request = client.calls[0]
    assert request["model"] == "meta-models/muse-spark-open"
    assert request["messages"][0]["role"] == "developer"
    assert request["messages"][1]["content"].startswith("You are Muse Spark")
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_completion_tokens"] == ask_muse.MAX_COMPLETION_TOKENS
    # Meta documents temperature=1.0 as the tuned default; we do not override it.
    assert "temperature" not in request
    assert "system" not in [message["role"] for message in request["messages"]]
    assert SECRET not in json.dumps(request)

    assert result["model"] == "meta-models/muse-spark-open"
    structured = result["structured"]
    assert list(structured) == ["sections", "claims"]
    assert [s["title"] for s in structured["sections"]] == list(
        ask_muse.REQUIRED_TITLES
    )
    assert "unexpected_field" not in structured["sections"][0]
    assert "unexpected_field" not in structured["claims"][0]


def test_fenced_json_is_accepted(fake_provider):
    fake_provider([make_response(as_content(valid_report(), fenced=True))])
    result = ask_muse.generate_interpretation(CONTEXT)
    assert len(result["structured"]["sections"]) == len(ask_muse.REQUIRED_TITLES)


def test_case_insensitive_titles_are_canonicalized():
    report = valid_report(section_titles=[t.upper() for t in ask_muse.REQUIRED_TITLES])
    result = ask_muse.validate_report(json.dumps(report))
    assert [s["title"] for s in result["sections"]] == list(ask_muse.REQUIRED_TITLES)


@pytest.mark.parametrize(
    "response, expected",
    [
        (make_response(""), "empty content"),
        (make_response(None), "empty content"),
        (make_response("   \n "), "empty content"),
        (make_response(as_content(valid_report()), choices=False), "no response choices"),
        (make_response(None, with_message=False), "without a message"),
        (make_response("not json at all"), "required JSON structure"),
        (make_response(json.dumps({"sections": [], "claims": []})), "required JSON structure"),
        (
            make_response("x" * (ask_muse.MAX_RAW_REPORT_CHARS + 10)),
            "oversized response",
        ),
        (
            make_response(as_content(valid_report()), finish_reason="length"),
            "truncated",
        ),
        (
            make_response(
                None,
                message_extra={"reasoning_content": "long internal reasoning"},
            ),
            "reasoning but no visible report",
        ),
    ],
)
def test_bad_provider_responses_are_rejected(fake_provider, response, expected):
    fake_provider([response])
    with pytest.raises(RuntimeError) as exc_info:
        ask_muse.generate_interpretation(CONTEXT)
    assert expected in str(exc_info.value)
    assert SECRET not in str(exc_info.value)


def test_reasoning_content_is_never_used_as_the_report(fake_provider):
    """The constraint: thinking text must not be substituted for a report."""
    fake_provider(
        [make_response(None, message_extra={"reasoning_content": json.dumps(valid_report())})]
    )
    with pytest.raises(RuntimeError, match="reasoning but no visible report"):
        ask_muse.generate_interpretation(CONTEXT)


@pytest.mark.parametrize(
    "status, expected",
    [
        (401, "BASETEN_API_KEY"),
        (403, "permissions"),
        (404, "model"),
        (429, "quota"),
        (500, "HTTP 500"),
        (503, "HTTP 503"),
    ],
)
def test_http_errors_are_actionable_and_secret_free(fake_provider, status, expected):
    fake_provider([HttpError(status)])
    with pytest.raises(RuntimeError) as exc_info:
        ask_muse.generate_interpretation(CONTEXT)
    message = str(exc_info.value)
    assert expected in message
    assert SECRET not in message


def test_http_400_retries_once_without_json_mode(fake_provider):
    created = fake_provider(
        [
            HttpError(400),
            make_response(as_content(valid_report())),
        ]
    )
    result = ask_muse.generate_interpretation(CONTEXT)

    assert len(result["structured"]["sections"]) == len(ask_muse.REQUIRED_TITLES)
    assert len(created[0].calls) == 2
    fallback = created[0].calls[1]
    assert "response_format" not in fallback
    assert "max_completion_tokens" not in fallback
    assert fallback["max_tokens"] == ask_muse.MAX_COMPLETION_TOKENS


def test_repeated_http_400_is_reported_not_retried_forever(fake_provider):
    created = fake_provider([HttpError(400)])
    with pytest.raises(RuntimeError, match="HTTP 400"):
        ask_muse.generate_interpretation(CONTEXT)
    assert len(created[0].calls) == 2


def test_network_error_is_generic_and_never_leaks_raw_exception(fake_provider):
    fake_provider([RuntimeError(f"connection to host failed with key {SECRET}")])
    with pytest.raises(RuntimeError) as exc_info:
        ask_muse.generate_interpretation(CONTEXT)
    message = str(exc_info.value)
    assert "Could not contact" in message
    assert SECRET not in message
    assert "connection to host failed" not in message


def test_oversized_context_is_a_local_error_not_a_provider_failure(fake_provider):
    created = fake_provider([])
    huge = {"results": {"blob": "x" * (ask_muse.MAX_CONTEXT_CHARS + 100)}}
    with pytest.raises(ValueError, match="too large"):
        ask_muse.generate_interpretation(huge)
    assert created == []  # no provider request was made


def test_missing_key_fails_before_any_request(fake_provider, monkeypatch):
    created = fake_provider([])
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY is missing"):
        ask_muse.generate_interpretation(CONTEXT)
    assert created == []


def test_model_can_be_overridden_for_hackathon_accounts(fake_provider, monkeypatch):
    created = fake_provider([make_response(as_content(valid_report()))])
    monkeypatch.setattr(ask_muse, "MODEL", "meta-models/muse-spark-open-1026")
    ask_muse.generate_interpretation(CONTEXT)
    assert created[0].calls[0]["model"] == "meta-models/muse-spark-open-1026"


def test_client_construction_failure_is_reported_safely(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", SECRET)

    def broken_factory(**kwargs):
        raise RuntimeError(f"bad client config with {SECRET}")

    monkeypatch.setattr(ask_muse, "OpenAI", broken_factory)
    with pytest.raises(RuntimeError) as exc_info:
        ask_muse.generate_interpretation(CONTEXT)
    assert "Could not contact" in str(exc_info.value)
    assert SECRET not in str(exc_info.value)


def test_fallback_attempt_network_failure_is_reported(fake_provider):
    fake_provider([HttpError(400), OSError(f"dns failure {SECRET}")])
    with pytest.raises(RuntimeError) as exc_info:
        ask_muse.generate_interpretation(CONTEXT)
    assert "Could not contact" in str(exc_info.value)
    assert SECRET not in str(exc_info.value)


def test_nan_in_context_is_rejected_before_json_encoding(fake_provider):
    fake_provider([])
    with pytest.raises(ValueError, match="could not be serialized"):
        ask_muse.build_prompt({"results": {"slope": float("nan")}})


def test_prompt_size_guard_is_enforced(monkeypatch):
    monkeypatch.setattr(ask_muse, "MAX_PROMPT_CHARS", 100)
    with pytest.raises(ValueError, match="size limit"):
        ask_muse.build_prompt(CONTEXT)


def test_validate_report_rejects_wrong_container_types():
    assert ask_muse.validate_report({"sections": "not a list", "claims": []}) is None
    assert ask_muse.validate_report({"sections": [], "claims": "not a list"}) is None
    assert ask_muse.validate_report(json.dumps([1, 2, 3])) is None
    assert ask_muse.validate_report(json.dumps("just a string")) is None

    blank_title = valid_report()
    blank_title["sections"][0]["title"] = "   "
    assert ask_muse.validate_report(blank_title) is None

    blank_content = valid_report()
    blank_content["sections"][0]["content"] = "   "
    assert ask_muse.validate_report(blank_content) is None

    bad_section = valid_report()
    bad_section["sections"][0] = "not a dict"
    assert ask_muse.validate_report(bad_section) is None

    bad_claim = valid_report()
    bad_claim["claims"][0] = "not a dict"
    assert ask_muse.validate_report(bad_claim) is None


def test_validate_report_enforces_all_size_and_shape_limits():
    good = valid_report()
    assert ask_muse.validate_report(good) is not None

    too_many_words = json.loads(json.dumps(good))
    too_many_words["sections"][0]["content"] = "word " * 26
    assert ask_muse.validate_report(too_many_words) is None

    too_long_content = json.loads(json.dumps(good))
    too_long_content["sections"][0]["content"] = "x" * (
        ask_muse.MAX_CONTENT_CHARS + 1
    )
    assert ask_muse.validate_report(too_long_content) is None

    too_long_claim = json.loads(json.dumps(good))
    too_long_claim["claims"][0]["claim"] = "x" * (
        ask_muse.MAX_CLAIM_FIELD_CHARS + 1
    )
    assert ask_muse.validate_report(too_long_claim) is None

    too_many_claims = json.loads(json.dumps(good))
    too_many_claims["claims"] = too_many_claims["claims"] * 3
    assert ask_muse.validate_report(too_many_claims) is None

    duplicate = json.loads(json.dumps(good))
    duplicate["sections"][1]["title"] = duplicate["sections"][0]["title"]
    assert ask_muse.validate_report(duplicate) is None

    unknown = json.loads(json.dumps(good))
    unknown["sections"][0]["title"] = "Unexpected Section"
    assert ask_muse.validate_report(unknown) is None

    missing_section = json.loads(json.dumps(good))
    missing_section["sections"].pop()
    assert ask_muse.validate_report(missing_section) is None

    missing_field = json.loads(json.dumps(good))
    del missing_field["claims"][0]["limitation"]
    assert ask_muse.validate_report(missing_field) is None

    empty_field = json.loads(json.dumps(good))
    empty_field["claims"][0]["evidence"] = "  "
    assert ask_muse.validate_report(empty_field) is None

    non_string = json.loads(json.dumps(good))
    non_string["sections"][0]["content"] = 42
    assert ask_muse.validate_report(non_string) is None

    assert ask_muse.validate_report("x" * (ask_muse.MAX_RAW_REPORT_CHARS + 1)) is None
    assert ask_muse.validate_report(None) is None
    assert ask_muse.validate_report(["not", "a", "dict"]) is None
    assert ask_muse.validate_report("```json\n{broken\n```") is None


def test_provider_status_messages_never_hold_credentials():
    for status in (400, 401, 403, 404, 408, 429, 500, 502, 503, 504, 418):
        message = ask_muse.describe_provider_status(status)
        assert str(status) in message
        assert SECRET not in message
    assert "Provider request failed" in ask_muse.describe_provider_status("weird")


def test_prompt_is_bounded_and_requires_every_section():
    prompt = ask_muse.build_prompt(CONTEXT)
    for title in ask_muse.REQUIRED_TITLES:
        assert title in prompt
    assert f"at most {ask_muse.MAX_SECTION_WORDS} words" in prompt
    assert f"at most {ask_muse.MAX_CLAIMS} claims" in prompt
    assert len(prompt) <= ask_muse.MAX_PROMPT_CHARS
    assert "no markdown code fences" in prompt
