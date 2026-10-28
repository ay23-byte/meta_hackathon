"""The manual Baseten probe must not run as a side effect of pytest collection."""

import runpy
from pathlib import Path

import openai

import provider_config


def test_importing_manual_probe_does_not_access_credentials_or_construct_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("manual provider probe ran during import")

    monkeypatch.setattr(provider_config, "get_api_key", forbidden)
    monkeypatch.setattr(openai, "OpenAI", forbidden)
    script = Path(__file__).resolve().parents[1] / "test_baseten.py"
    runpy.run_path(str(script), run_name="test_baseten_import")
