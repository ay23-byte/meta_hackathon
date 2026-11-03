"""Central dispatch for explicitly requested scientific report generation.

This module does not retry or substitute one provider for another.  The
underlying adapters own their provider-specific transport and validation.
"""
from __future__ import annotations

import ask_muse
import provider_config


class UnsupportedProviderError(ValueError):
    """The selected provider is not available in this router."""


def generate_interpretation(context: dict, section_titles=None, *,
                            profile=ask_muse.DEFAULT_REPORT_PROFILE,
                            confirmed: bool = False) -> dict:
    """Dispatch a live report to the selected adapter, preserving provenance."""
    mode = provider_config.selected_ai_provider()
    if mode == "nvidia":
        import hosted_model_provider

        wrapper = hosted_model_provider.generate_interpretation(
            context, section_titles, profile=profile, confirmed=confirmed)
        expected_source = "hosted_model"
    elif mode == "ollama":
        import local_meta_provider

        wrapper = local_meta_provider.generate_scientific_report(
            context, section_titles, profile=profile, model=provider_config.get_ollama_model())
        expected_source = "local_ollama"
    elif mode in ("", "baseten"):
        if not provider_config.get_api_key():
            raise RuntimeError("BASETEN_API_KEY is not configured; deterministic analysis remains available.")
        if profile == ask_muse.DEFAULT_REPORT_PROFILE:
            wrapper = ask_muse.generate_interpretation(context, section_titles=section_titles)
        else:
            wrapper = ask_muse.generate_interpretation(context, section_titles=section_titles, profile=profile)
        return ask_muse.enforce_report_provenance(wrapper, "live")
    else:
        raise UnsupportedProviderError("Unsupported provider selection; no provider was called.")
    if (not isinstance(wrapper, dict) or wrapper.get("is_mock") is not False
            or wrapper.get("source") != expected_source):
        raise RuntimeError("Selected provider returned invalid provenance.")
    return wrapper
