"""Explicit, local-only Ollama adapter for Meta Llama 3.2 1B.

No network request occurs on import. Only a fixed loopback endpoint is used;
no proxy, redirects, model downloads, remote fallbacks, or generated code.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import ask_muse
from ai_guard import check_report_numbers

BASE_URL = "http://127.0.0.1:11434"
MODEL = "llama3.2:1b"
PROVIDER = "Meta Llama 3.2 1B — Local Ollama"
TIMEOUT = 120
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(path: str, payload: dict | None = None, *, timeout: int = TIMEOUT) -> dict:
    if path not in ("/api/tags", "/api/chat"):
        raise ValueError("Unsupported Ollama API path.")
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(BASE_URL + path, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST" if body is not None else "GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except TimeoutError:
        raise RuntimeError("Ollama request timed out; local analysis is still available.") from None
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ollama returned HTTP {exc.code}; no report was generated.") from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise RuntimeError("Ollama request timed out; local analysis is still available.") from None
        raise RuntimeError("Cannot connect to local Ollama at 127.0.0.1:11434. Start Ollama locally.") from None
    except OSError:
        raise RuntimeError("Cannot connect to local Ollama at 127.0.0.1:11434. Start Ollama locally.") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Ollama response exceeded the size limit.")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Ollama returned malformed JSON.") from None
    if not isinstance(data, dict):
        raise RuntimeError("Ollama returned an invalid response.")
    return data


def check_ollama_status() -> dict:
    """Check availability only when explicitly called; never initiate a model download."""
    try:
        data = _request("/api/tags", timeout=5)
    except RuntimeError as exc:
        return {"running": False, "model_available": False, "message": str(exc)}
    models = data.get("models")
    if not isinstance(models, list):
        return {"running": True, "model_available": False, "message": "Ollama returned an invalid model list."}
    available = any(isinstance(item, dict) and (item.get("name") == MODEL or item.get("model") == MODEL)
                    for item in models)
    return {"running": True, "model_available": available,
            "message": "Model available." if available else "Model not installed; install it manually with ollama pull llama3.2:1b."}


def check_model_available() -> bool:
    return check_ollama_status()["model_available"]


def generate_scientific_report(context: dict, section_titles=None, *, profile=ask_muse.DEFAULT_REPORT_PROFILE) -> dict:
    """Generate and strictly validate the existing report schema, no fallback."""
    titles = ask_muse.resolve_section_titles(section_titles, profile=profile)
    prompt = ask_muse.build_prompt(context, titles, profile=profile).replace(
        "You are Muse Spark, an assistant for scientific experiment analysis.",
        "You are Meta Llama 3.2 1B, a local assistant for scientific experiment analysis.", 1)
    status = check_ollama_status()
    if not status["running"] or not status["model_available"]:
        raise RuntimeError(status["message"])
    data = _request("/api/chat", {"model": MODEL, "stream": False, "format": "json",
                                  "options": {"temperature": 0.1, "num_predict": 2048},
                                  "messages": [{"role": "user", "content": prompt}]})
    if data.get("model") is not None and data.get("model") != MODEL:
        raise RuntimeError("Ollama returned a response for a different model; no report was stored.")
    if data.get("done") is not True or data.get("done_reason") in ("length", "load"):
        raise RuntimeError("Ollama response was incomplete; no report was stored.")
    message = data.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned no visible report content.")
    structured = ask_muse.validate_report(content, titles, profile=profile,
                                          allowed_evidence_ids=context.get("result_ids"))
    if structured is None:
        raise RuntimeError("Local Llama output did not match the required report schema or evidence IDs.")
    guard = check_report_numbers(structured, context)
    if guard["status"] == "contradiction":
        raise RuntimeError("Local Llama output contradicts computed values or evidence IDs.")
    return {"source": "local_ollama", "provider": PROVIDER, "model": MODEL, "is_mock": False,
            "provider_status": "local_response_validated", "profile": profile,
            "numeric_guard": guard, "evidence_index": context.get("evidence_index", {}),
            "structured": structured}


def interpret_experiment(context: dict, section_titles=None, *, profile=ask_muse.DEFAULT_REPORT_PROFILE) -> dict:
    return generate_scientific_report(context, section_titles, profile=profile)


def ask_scientific_question(question: str, context: dict, section_titles=None, *, profile=ask_muse.DEFAULT_REPORT_PROFILE) -> dict:
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("Enter a scientific question of 1 to 500 characters.")
    scoped = dict(context)
    scoped["research_question"] = question.strip()
    return generate_scientific_report(scoped, section_titles, profile=profile)
