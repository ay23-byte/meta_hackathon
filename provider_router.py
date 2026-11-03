"""Central dispatch for explicitly requested scientific report generation.

This module does not retry or substitute one provider for another.  The
underlying adapters own their provider-specific transport and validation.
"""
from __future__ import annotations

import ask_muse
import provider_config


def _contains_secret(value) -> bool:
    """Inspect context and output strings without rendering secrets in errors."""
    if isinstance(value, str):
        return provider_config.redact(value) != value
    if isinstance(value, dict):
        return any(_contains_secret(key) or _contains_secret(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item) for item in value)
    return False


class UnsupportedProviderError(ValueError):
    """The selected provider is not available in this router."""


def generate_interpretation(context: dict, section_titles=None, *,
                            profile=ask_muse.DEFAULT_REPORT_PROFILE,
                            confirmed: bool = False, model: str | None = None) -> dict:
    """Dispatch a live report to the selected adapter, preserving provenance."""
    mode = provider_config.selected_ai_provider()
    # Build once before dispatch to enforce existing prompt limits and detect
    # credentials in the original values, including JSON-escaped strings.
    ask_muse.build_prompt(context, section_titles, profile=profile)
    if _contains_secret(context):
        raise ValueError("Analysis context contains credential material; no provider request was made.")
    if mode in ("nvidia", "hosted"):
        import hosted_model_provider

        wrapper = hosted_model_provider.generate_interpretation(
            context, section_titles, profile=profile, confirmed=confirmed)
        expected_source = "hosted_model"
    elif mode == "ollama":
        import local_meta_provider

        wrapper = local_meta_provider.generate_scientific_report(
            context, section_titles, profile=profile, model=model or provider_config.get_ollama_model())
        expected_source = "local_ollama"
    elif mode == "baseten":
        if not provider_config.get_api_key():
            raise RuntimeError("BASETEN_API_KEY is not configured; deterministic analysis remains available.")
        if profile == ask_muse.DEFAULT_REPORT_PROFILE and section_titles is None:
            wrapper = ask_muse.generate_interpretation(context)
        elif profile == ask_muse.DEFAULT_REPORT_PROFILE:
            wrapper = ask_muse.generate_interpretation(context, section_titles=section_titles)
        else:
            wrapper = ask_muse.generate_interpretation(context, section_titles=section_titles, profile=profile)
        wrapper = ask_muse.enforce_report_provenance(wrapper, "live")
        expected_source = ask_muse.LIVE_REPORT_SOURCE
    else:
        raise UnsupportedProviderError("Unsupported provider selection; no provider was called.")
    if (not isinstance(wrapper, dict) or wrapper.get("is_mock") is not False
            or wrapper.get("source") != expected_source):
        raise RuntimeError("Selected provider returned invalid provenance.")
    if _contains_secret(wrapper):
        raise RuntimeError("Provider output contains credential material and was rejected.")
    if mode == "nvidia" and (wrapper.get("provider") != "NVIDIA NIM"
                             or wrapper.get("model") != provider_config.get_nvidia_model()):
        raise RuntimeError("Selected NVIDIA provider returned mismatched provenance.")
    if mode == "ollama" and (wrapper.get("model") != (model or provider_config.get_ollama_model())
                             or wrapper.get("provider") != local_meta_provider.SUPPORTED_MODELS.get(wrapper.get("model"))):
        raise RuntimeError("Selected Ollama provider returned mismatched provenance.")
    return wrapper


def request_plan(prompt: str, *, max_tokens: int, confirmed: bool = False) -> str:
    """Request visible plan text from exactly the selected provider.

    The caller must parse and validate this untrusted text before execution.
    """
    if confirmed is not True:
        raise ValueError("Explicit consent is required before requesting an AI plan.")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > ask_muse.MAX_PROMPT_CHARS:
        raise ValueError("Planning prompt is empty or exceeds the size limit.")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= 4096:
        raise ValueError("Invalid plan token budget.")
    if provider_config.redact(prompt) != prompt:
        raise ValueError("Planning context contains credential material.")
    mode = provider_config.selected_ai_provider()
    if mode in ("nvidia", "hosted"):
        import hosted_model_provider

        config = hosted_model_provider._config()
        config["tokens"] = max_tokens
        content, _ = hosted_model_provider._request_content(config, prompt)
    elif mode == "ollama":
        import local_meta_provider

        model = local_meta_provider._validate_model(provider_config.get_ollama_model())
        status = local_meta_provider.check_ollama_status(model)
        if not status["model_available"]:
            raise RuntimeError("Local model is unavailable; no plan was generated.")
        response = local_meta_provider._request("/api/chat", {
            "model": model, "stream": False, "format": "json",
            "options": {"temperature": 0.1, "num_predict": max_tokens},
            "messages": [{"role": "user", "content": prompt}],
        })
        if response.get("model") not in (None, model):
            raise RuntimeError("Ollama returned a different model identifier.")
        if response.get("done") is not True or response.get("done_reason") in ("length", "load"):
            raise RuntimeError("Ollama returned an incomplete plan.")
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
    elif mode == "baseten":
        provider_config.require_baseten_selection()
        key = provider_config.get_api_key()
        if not key:
            raise RuntimeError("BASETEN_API_KEY is not configured.")
        client = ask_muse.OpenAI(api_key=key, base_url=ask_muse.BASE_URL,
                                timeout=ask_muse.REQUEST_TIMEOUT_SECONDS, max_retries=0)
        try:
            response = ask_muse._completion_request(
                client, prompt, json_mode=True, modern_tokens=True, max_tokens=max_tokens)
            choices = getattr(response, "choices", None)
            choice = choices[0] if choices else None
            message = getattr(choice, "message", None)
            if (getattr(choice, "finish_reason", None) in ("length", "content_filter", "tool_calls", "function_call")
                    or getattr(message, "refusal", None)):
                raise RuntimeError("Baseten did not return a complete plan.")
            content = getattr(message, "content", None)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
    else:
        raise UnsupportedProviderError("Unsupported provider selection; no provider was called.")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Selected provider returned no visible plan content.")
    if len(content) > 64_000 or provider_config.redact(content) != content:
        raise RuntimeError("Selected provider returned an unsafe plan response.")
    return content
