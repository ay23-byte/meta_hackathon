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
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
BASE_URL = "https://inference.baseten.co/v1"
DEFAULT_MODEL = "meta-models/muse-spark-open"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_KEY_ENV = "NVIDIA_API_KEY"
NVIDIA_MODEL_ENV = "NVIDIA_MODEL"
NVIDIA_DEFAULT_MODEL = "meta/muse-glimmer-30b"
AI_PROVIDER_ENV = "LABLENS_AI_PROVIDER"
# Use the project file first; retain the previously requested Windows path as
# an explicit fallback when the project-local file does not exist.
NVIDIA_ENV_FILE: Path | None = None
NVIDIA_LEGACY_ENV_FILE = Path(r"F:\meta-hacathon\.env") if os.name == "nt" else None


def _nvidia_env_file() -> Path:
    """Choose one file; an explicit override never falls back to another file."""
    if NVIDIA_ENV_FILE is not None:
        return Path(NVIDIA_ENV_FILE)
    path = Path(ENV_FILE)
    if path == ROOT / ".env" and not path.is_file() and NVIDIA_LEGACY_ENV_FILE is not None:
        return NVIDIA_LEGACY_ENV_FILE
    return path


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
_file_values_signature: tuple | None = None


def dotenv_enabled() -> bool:
    """Return False when tests/CI explicitly disable local .env fallback."""
    return os.getenv(DISABLE_DOTENV_ENV, "").strip().casefold() not in _TRUE_VALUES


def reload_dotenv() -> None:
    """Forget every cached value and file signature."""
    global _file_values, _file_values_signature
    _file_values = None
    _file_values_signature = None


def _read_dotenv() -> dict[str, str]:
    """Read one selected file, without environment mutation or interpolation."""
    global _file_values, _file_values_signature
    if not dotenv_enabled():
        return {}
    path = _nvidia_env_file()
    try:
        stat = path.stat()
        signature = (path, stat.st_mtime_ns, stat.st_size, stat.st_ino)
    except OSError:
        signature = (path, None)
    if _file_values is None or _file_values_signature != signature:
        try:
            _file_values = {str(key): (value.strip() if isinstance(value, str) else "")
                            for key, value in dotenv_values(path, interpolate=False).items()
                            if isinstance(key, str)}
        except (OSError, UnicodeError):
            _file_values = {}
        _file_values_signature = signature
    return _file_values


def _process_value(name: str) -> str:
    raw = os.getenv(name)
    return raw.strip() if raw and raw.strip() else ""


def get_setting(name: str, default: str = "") -> str:
    """Process environment wins; .env is a fallback when not disabled."""
    if name in os.environ:
        return os.environ[name].strip()
    if dotenv_enabled():
        file_value = _read_dotenv().get(name, "")
        if file_value:
            return file_value
    return default


def nvidia_setting(name: str) -> str:
    """Process environment wins (including blank); otherwise read the NVIDIA dotenv file."""
    if name not in (NVIDIA_KEY_ENV, NVIDIA_MODEL_ENV):
        raise ValueError("Unsupported NVIDIA setting.")
    if name in os.environ:
        return os.environ[name].strip()
    return _read_dotenv().get(name, "")


def get_nvidia_model() -> str:
    """Use the documented model only when no override was supplied at all."""
    if NVIDIA_MODEL_ENV in os.environ:
        return os.environ[NVIDIA_MODEL_ENV].strip()
    values = _read_dotenv()
    return values[NVIDIA_MODEL_ENV] if NVIDIA_MODEL_ENV in values else NVIDIA_DEFAULT_MODEL


def selected_ai_provider() -> str:
    """An explicitly blank provider fails closed; no network access occurs here."""
    if AI_PROVIDER_ENV in os.environ:
        return os.environ[AI_PROVIDER_ENV].strip().lower() or "invalid-empty-provider"
    values = _read_dotenv()
    if AI_PROVIDER_ENV in values:
        return values[AI_PROVIDER_ENV].strip().lower() or "invalid-empty-provider"
    return "nvidia"



def get_provider() -> str:
    """Return an explicitly supported provider or reject the configuration."""
    mode = selected_ai_provider()
    if mode not in ("nvidia", "baseten", "ollama", "hosted"):
        raise ValueError("Unsupported LABLENS_AI_PROVIDER; no provider was called.")
    return mode


def get_api_env() -> str:
    return {"nvidia": NVIDIA_KEY_ENV, "baseten": KEY_ENV, "ollama": "", "hosted": "LABLENS_API_KEY"}[get_provider()]


def get_model_env() -> str:
    return {"nvidia": NVIDIA_MODEL_ENV, "baseten": MODEL_ENV, "ollama": "OLLAMA_MODEL", "hosted": "LABLENS_MODEL"}[get_provider()]


def get_base_url() -> str:
    mode = get_provider()
    if mode == "nvidia":
        return NVIDIA_BASE_URL
    if mode == "baseten":
        return BASE_URL
    if mode == "ollama":
        return get_ollama_host()
    return os.environ.get("LABLENS_BASE_URL", "").strip()

def require_baseten_selection() -> None:
    """Fail closed before a legacy adapter can contact an unintended provider."""
    if selected_ai_provider() != "baseten":
        raise RuntimeError("The selected provider cannot be used by the legacy Baseten adapter; no provider request was made.")


def setting_source(name: str) -> str:
    """Human-readable, secret-free origin of a configured setting."""
    if name in os.environ:
        return "process environment" if _process_value(name) else "none"
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
    name = get_api_env()
    key = (os.environ.get(name, "").strip() if selected_ai_provider() == "hosted" else get_setting(name)) if name else ""
    source = setting_source(name) if name else "none"
    env_file_present = _nvidia_env_file().is_file() if dotenv_enabled() else False
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


def get_report_token_budget() -> int:
    """Bound an optional live-report budget; invalid settings fail before a request."""
    raw = get_setting("LABLENS_REPORT_MAX_TOKENS", "4096")
    if not raw.isascii() or not raw.isdecimal():
        raise ValueError("LABLENS_REPORT_MAX_TOKENS must be an integer from 1024 to 16384.")
    value = int(raw)
    if not 1024 <= value <= 16384:
        raise ValueError("LABLENS_REPORT_MAX_TOKENS must be an integer from 1024 to 16384.")
    return value


def get_baseten_model() -> str:
    """Return the Baseten model independently of the selected provider."""
    return get_setting(MODEL_ENV, DEFAULT_MODEL)


def get_model() -> str:
    """Return the model configured for the selected provider."""
    mode = get_provider()
    if mode == "nvidia":
        return get_nvidia_model()
    if mode == "baseten":
        return get_baseten_model()
    if mode == "ollama":
        return get_ollama_model()
    return os.environ.get("LABLENS_MODEL", "meta-models/Muse-Glimmer-30B").strip()


def get_ollama_model() -> str:
    """Configured local model, preserving explicit blank overrides."""
    return get_setting("OLLAMA_MODEL", "llama3.2:1b")


def get_ollama_host() -> str:
    """Return a loopback-only Ollama origin, never a remote endpoint."""
    host = get_setting("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        parts = urlsplit(host)
        if (parts.scheme != "http" or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment
                or parts.port is None):
            raise ValueError
    except ValueError:
        raise ValueError("OLLAMA_HOST must be an HTTP loopback origin with an explicit port and no credentials or path.") from None
    return host.rstrip("/")


def secret_values() -> list[str]:
    """Values that must be redacted from user-visible error messages.

    Includes both a process-env key and a local .env key so a developer
    machine cannot leak either one through an exception string.
    """
    values: list[str] = []
    for name in (NVIDIA_KEY_ENV, KEY_ENV, "LABLENS_API_KEY", "BLUESMINDS_API_KEY"):
        process_key = os.getenv(name)
        if process_key and not is_placeholder(process_key):
            values.append(process_key.strip())
        file_key = _read_dotenv().get(name, "")
        if file_key and not is_placeholder(file_key):
            values.append(file_key)
    return list(dict.fromkeys(values))


def redact(text: str) -> str:
    """Replace every known configured secret in a string with a marker."""
    safe = str(text)
    for value in secret_values():
        if value:
            safe = safe.replace(value, "[redacted]")
    return safe
