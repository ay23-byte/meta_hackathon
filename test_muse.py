"""Optional LIVE Muse Spark integration tests (explicit opt-in only).

These are skipped during an ordinary ``pytest`` run. They are selected only
when BOTH conditions hold:

1. ``--run-live`` is supplied (see ``tests/conftest.py``); and
2. a usable ``BASETEN_API_KEY`` is available from the process environment or
   the project-local ``.env`` file through ``provider_config``.

Run deliberately with:

    python -m pytest --run-live -m live -v

They make real provider calls that may consume credits. Offline contract tests
for the same adapter live in ``tests/test_ask_muse_provider.py`` and
``tests/test_provider_hardening.py`` and use a fake client; a green offline
suite is NOT evidence that the live endpoint works. Keep those two facts
separate in any report.
"""

import pytest
from openai import APIConnectionError, APITimeoutError, OpenAI

import ask_muse
import provider_config

pytestmark = pytest.mark.live


def _require_key() -> str:
    status = provider_config.api_key_status()
    if not status["present"]:
        pytest.skip(
            "BASETEN_API_KEY is not configured or is an obvious placeholder. "
            "Live tests require --run-live and a real key."
        )
    return status["key"]


def _client(api_key: str, timeout: float = 30.0):
    return OpenAI(
        api_key=api_key,
        base_url=provider_config.BASE_URL,
        timeout=timeout,
        max_retries=0,
    )


def _skip_if_provider_unreachable(exc: Exception) -> None:
    """Network/DNS/TLS unavailability is an environment skip, not a code bug."""
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        pytest.skip(f"Muse Spark endpoint is unreachable in this environment: {type(exc).__name__}")
    if isinstance(exc, RuntimeError) and (
        "Could not contact the Muse Spark provider" in str(exc)
        or "request timed out" in str(exc)
    ):
        pytest.skip(f"Muse Spark endpoint is unreachable in this environment: {exc}")


def test_muse_spark_connectivity():
    """A minimal round-trip: the endpoint must return usable text."""
    api_key = _require_key()
    try:
        response = _client(api_key).chat.completions.create(
            model=ask_muse.MODEL,
            messages=[{"role": "user", "content": "Reply with exactly: Hello World"}],
            stream=False,
            max_tokens=64,
        )
    except (APIConnectionError, APITimeoutError) as exc:
        _skip_if_provider_unreachable(exc)
        raise

    if not response.choices:
        pytest.fail("Muse Spark returned no response choices.")

    text = response.choices[0].message.content
    if not isinstance(text, str) or not text.strip():
        pytest.fail("Muse Spark returned empty or unusable content.")
    if "hello" not in text.casefold() or "world" not in text.casefold():
        pytest.fail(f"Muse Spark did not follow the instruction: {text!r}")


def test_muse_spark_structured_report():
    """The live end-to-end path the dashboard actually uses."""
    _require_key()
    context = {
        "scientific_question": "How does voltage vary with current?",
        "model": "V = mI + b (ordinary least squares)",
        "results": {
            "slope": 5.0,
            "intercept": 0.01,
            "r_squared": 0.9999,
            "rmse": 0.02,
            "n": 11,
        },
        "limitations": [
            "Instrument uncertainty is not available.",
            "Provenance is not independently verified.",
        ],
    }

    try:
        report = ask_muse.generate_interpretation(context)
    except (APIConnectionError, APITimeoutError, RuntimeError) as exc:
        _skip_if_provider_unreachable(exc)
        raise

    assert isinstance(report, dict)
    structured = ask_muse.validate_report(report["structured"])
    assert structured is not None, "Live report failed the strict schema."
    assert [s["title"] for s in structured["sections"]] == list(
        ask_muse.REQUIRED_TITLES
    )
    assert len(structured["claims"]) <= ask_muse.MAX_CLAIMS
