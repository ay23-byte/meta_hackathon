"""Optional LIVE Muse Spark integration tests (never run in offline CI).

These are skipped unless BASETEN_API_KEY is set. Run deliberately with:

    python -m pytest -m live -v

They make real provider calls that may consume credits. Offline contract
tests for the same adapter live in tests/test_ask_muse_provider.py and use a
fake client; a green offline suite is NOT evidence that the live endpoint
works. Keep those two facts separate in any report.
"""

import os

import pytest
from openai import OpenAI

import ask_muse

pytestmark = pytest.mark.live


def _client(timeout=30.0):
    return OpenAI(
        api_key=os.environ["BASETEN_API_KEY"],
        base_url="https://inference.baseten.co/v1",
        timeout=timeout,
        max_retries=0,
    )


def _require_key():
    if not os.getenv("BASETEN_API_KEY"):
        pytest.skip("BASETEN_API_KEY is not configured.")


def test_muse_spark_connectivity():
    """A minimal round-trip: the endpoint must return usable text."""
    _require_key()
    response = _client().chat.completions.create(
        model=ask_muse.MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: Hello World"}],
        stream=False,
        max_tokens=64,
    )

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

    report = ask_muse.generate_interpretation(context)

    assert isinstance(report, dict)
    structured = ask_muse.validate_report(report["structured"])
    assert structured is not None, "Live report failed the strict schema."
    assert [s["title"] for s in structured["sections"]] == list(
        ask_muse.REQUIRED_TITLES
    )
    assert len(structured["claims"]) <= ask_muse.MAX_CLAIMS
