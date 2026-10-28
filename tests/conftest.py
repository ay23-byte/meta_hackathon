"""Global test isolation for the optional Muse Spark provider.

Historical failure root cause: app modules called ``load_dotenv`` at import
time, so a developer's real ``.env`` could repopulate ``BASETEN_API_KEY`` after
a test deliberately deleted it. Missing-key tests then failed and live tests
attempted real network calls during an ordinary ``pytest`` run.

The application now reads ``.env`` through ``provider_config`` without mutating
``os.environ``. These fixtures add two additional safety layers:

* every non-live test disables local ``.env`` fallback and starts with no key;
* live tests are skipped unless ``--run-live`` is explicitly supplied.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run opt-in live Baseten/Muse Spark integration tests (may consume credits).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(
        reason="live provider test requires --run-live; "
               "run: python -m pytest --run-live -m live -v"
    )
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def isolate_provider_environment(request, monkeypatch):
    """No unit test may inherit a developer key or trigger a live API call."""
    if request.node.get_closest_marker("live"):
        # Explicitly opt-in live tests may use a real process env / .env key.
        monkeypatch.delenv("LABLENS_DISABLE_DOTENV", raising=False)
        return
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_MODEL", raising=False)
    monkeypatch.delenv("LABLENS_REPORT_MAX_TOKENS", raising=False)
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
