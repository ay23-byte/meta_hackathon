"""Configurable AI report sections preserve the strict legacy default."""

import json

import pytest

import ask_muse


def valid_report(titles):
    return {
        "sections": [{"title": title, "content": f"Short note {i}."}
                     for i, title in enumerate(titles)],
        "claims": [],
    }


def test_default_is_the_original_eight_titles():
    assert ask_muse.DEFAULT_SECTION_TITLES == ask_muse.REQUIRED_TITLES
    assert len(ask_muse.REQUIRED_TITLES) == 8
    assert len(ask_muse.SECTION_REGISTRY) == ask_muse.MAX_SECTIONS == 10
    assert set(ask_muse.REQUIRED_TITLES).issubset(ask_muse.SECTION_REGISTRY)


def test_all_ten_sections_are_available_and_validated():
    titles = list(ask_muse.SECTION_REGISTRY)
    assert ask_muse.resolve_section_titles(titles) == tuple(titles)
    assert ask_muse.validate_report(valid_report(titles), titles) is not None
    prompt = ask_muse.build_prompt({"results": {"n": 3}}, titles)
    for title in titles:
        assert title in prompt
    assert "10 sections exactly once" in prompt


def test_canonicalization_and_validation_of_custom_subsets():
    titles = ["data quality and cleaning", "QUANTITATIVE RESULTS"]
    resolved = ask_muse.resolve_section_titles(titles)
    assert resolved == ("Data Quality and Cleaning", "Quantitative Results")
    result = ask_muse.validate_report(valid_report(titles), titles)
    assert [section["title"] for section in result["sections"]] == list(resolved)


@pytest.mark.parametrize("bad", [
    ["Executive Summary", "executive summary"],
    ["Not A Section"],
    ["Executive Summary", 3],
    [""],
    ["Executive Summary"] * 11,
    "Executive Summary",
    [],
])
def test_invalid_section_requests_are_rejected(bad):
    with pytest.raises(ValueError):
        ask_muse.resolve_section_titles(bad)


def test_validation_rejects_unexpected_or_duplicate_section_names():
    titles = ["Executive Summary", "Conclusion"]
    report = valid_report(["Executive Summary", "Executive Summary"])
    assert ask_muse.validate_report(report, titles) is None
    assert ask_muse.validate_report(
        {"sections": [{"title": "Conclusion", "content": "ok"},
                      {"title": "Alternative Explanations", "content": "ok"}],
         "claims": []}, titles) is None


def test_default_validation_rejects_extra_even_registered_sections():
    report = valid_report(ask_muse.REQUIRED_TITLES)
    report["sections"].append({"title": "Alternative Explanations", "content": "Extra."})
    assert ask_muse.validate_report(report) is None


def test_case_insensitive_canonicalization_still_works_with_default():
    report = valid_report([title.upper() for title in ask_muse.REQUIRED_TITLES])
    result = ask_muse.validate_report(json.dumps(report))
    assert [section["title"] for section in result["sections"]] == list(ask_muse.REQUIRED_TITLES)


def test_generate_interpretation_validates_local_section_config_before_network(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Unexpected report section"):
        ask_muse.generate_interpretation({"results": {}}, section_titles=["Invented"])


def test_custom_sections_pass_through_generate_interpretation(monkeypatch):
    # Stub the provider client locally: this test needs no network access.
    import types

    titles = ["Data Quality and Cleaning", "Quantitative Results"]
    content = json.dumps(valid_report(titles))
    message = types.SimpleNamespace(content=content, model_extra={})
    response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=message, finish_reason="stop")],
        model="test-model",
    )

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            return types.SimpleNamespace(completions=types.SimpleNamespace(
                create=lambda **kwargs: response
            ))

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    monkeypatch.setattr(ask_muse, "OpenAI", FakeClient)
    result = ask_muse.generate_interpretation({"results": {"n": 3}}, section_titles=titles)
    assert [s["title"] for s in result["structured"]["sections"]] == titles
