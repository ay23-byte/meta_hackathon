"""Single source of truth for optional Muse Spark / Baseten configuration.

Design goals (hackathon hardening, Phase B/C):

* Never mutate ``os.environ`` at import time. Importing an app or adapter must
  not silently repopulate a key after a test, deployment or user deliberately
  cleared it. ``python-dotenv`` is read with ``dotenv_values`` instead.
* Real process environment variables always win over the local ``.env`` file.
  This prevents an unintended local value from replacing a deployment secret.
* Missing, blank and obvious placeholder keys are reported as *not configured*.
* Tests and CI can disable ``.env`` reads with ``LABLENS_DISABLE_DOTENV=1``
  without changing application code.
* No key value is ever returned by a status function or included in a log.

This module performs no network calls and imports no OpenAI client.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BASE_URL = "https://inference.baseten.co/v1"
DEFAULT_MODEL = "meta-models/muse-spark-open"

KEY_ENV = "BASETEN_API_KEY"
MODEL_ENV = "BASETEN_MODEL"
DISABLE_DOTENV_ENV = "LABLENS_DISABLE_DOTENV"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_PLACEHOLDER_EXACT = frozenset({
    "your_baseten_api_key_here",
    "your_api_key_here",
    "your-key-here",
    "changeme",
    "change_me",
    "replace_me",
    "paste_your_key_here",
    "example_key",
    "dummy_key",
    "test_key",
})
_PLACEHOLDER_PREFIXES = (
    "your_", "paste_", "replace_", "insert_", "example_", "dummy_", "<",
)

_file_values: dict[str, str] | None = None
_file_values_path: Path | None = None


def dotenv_enabled() -> bool:
    """Return False when tests/CI explicitly disable local .env fallback."""
    return os.getenv(DISABLE_DOTENV_ENV, "").strip().casefold() not in _TRUE_VALUES


def reload_dotenv() -> None:
    """Forget cached .env values (useful after a test creates a temp .env)."""
    global _file_values, _file_values_path
    _file_values = None
    _file_values_path = None


def _read_dotenv() -> dict[str, str]:
    """Read .env without mutating os.environ; cache by resolved file path."""
    global _file_values, _file_values_path
    if _file_values is None or _file_values_path != ENV_FILE:
        if not ENV_FILE.is_file():
            _file_values = {}
        else:
            try:
                _file_values = {
                    str(key): value.strip()
                    for key, value in dotenv_values(ENV_FILE).items()
                    if isinstance(key, str) and isinstance(value, str) and value.strip()
                }
            except Exception:  # pragma: no cover - unreadable/odd .env file
                _file_values = {}
        _file_values_path = ENV_FILE
    return _file_values


def _process_value(name: str) -> str:
    raw = os.getenv(name)
    return raw.strip() if raw and raw.strip() else ""


def get_setting(name: str, default: str = "") -> str:
    """Process environment wins; .env is a fallback when not disabled."""
    process_value = _process_value(name)
    if process_value:
        return process_value
    if dotenv_enabled():
        file_value = _read_dotenv().get(name, "")
        if file_value:
            return file_value
    return default


def setting_source(name: str) -> str:
    """Human-readable, secret-free origin of a configured setting."""
    if _process_value(name):
        return "process environment"
    if dotenv_enabled() and _read_dotenv().get(name):
        return ".env (local project file)"
    return "none"


def is_placeholder(value: str | None) -> bool:
    """Detect obvious sample values from .env.example, not real credentials.

    Deliberately conservative: a generic test key such as
    ``unit-test-placeholder`` is NOT classified as a placeholder, so mocked
    provider tests can still exercise client construction.
    """
    if not isinstance(value, str):
        return True
    text = value.strip()
    if not text:
        return True
    lowered = text.casefold()
    if lowered in _PLACEHOLDER_EXACT:
        return True
    if any(lowered.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES):
        return True
    return "..." in text or "…" in text


def api_key_status() -> dict:
    """Return secret-free state plus the raw key for internal provider calls.

    ``key`` is present only in this internal dict. Never serialize it to the
    UI, an export, a log, or ``provider_status()``.
    """
    key = get_setting(KEY_ENV)
    source = setting_source(KEY_ENV)
    env_file_present = ENV_FILE.is_file()
    if not key:
        return {
            "present": False, "state": "missing", "key": None,
            "source": "none", "env_file_present": env_file_present,
        }
    if is_placeholder(key):
        return {
            "present": False, "state": "placeholder", "key": None,
            "source": source, "env_file_present": env_file_present,
        }
    return {
        "present": True, "state": "configured", "key": key,
        "source": source, "env_file_present": env_file_present,
    }


def get_api_key() -> str | None:
    """Return a usable key, or None for missing/blank/placeholder values."""
    return api_key_status()["key"]


def get_model() -> str:
    """Return the configured model, honoring process-env precedence."""
    return get_setting(MODEL_ENV, DEFAULT_MODEL)


def secret_values() -> list[str]:
    """Values that must be redacted from user-visible error messages.

    Includes both a process-env key and a local .env key so a developer
    machine cannot leak either one through an exception string.
    """
    values: list[str] = []
    raw_process = os.getenv(KEY_ENV)
    if raw_process and raw_process.strip() and not is_placeholder(raw_process):
        values.append(raw_process.strip())
    file_value = _read_dotenv().get(KEY_ENV, "")
    if file_value and not is_placeholder(file_value):
        values.append(file_value)
    return list(dict.fromkeys(values))


def redact(text: str) -> str:
    """Replace every known configured secret in a string with a marker."""
    safe = str(text)
    for value in secret_values():
        if value:
            safe = safe.replace(value, "[redacted]")
    return safe
