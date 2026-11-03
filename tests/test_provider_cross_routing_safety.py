"""Cross-provider guard tests; all clients must remain offline."""

import pytest

import agent_planner
import ask_muse


@pytest.mark.parametrize("mode", ["nvidia", "hosted", "ollama", "bluesminds", "unknown"])
def test_legacy_adapter_never_calls_baseten_for_another_selection(monkeypatch, mode):
    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-baseten-fake")
    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kwargs: pytest.fail("wrong provider contacted"))
    with pytest.raises(RuntimeError, match="selected provider"):
        ask_muse.generate_interpretation({"results": {"n": 3}})
    with pytest.raises(RuntimeError, match="selected provider"):
        ask_muse.check_provider_connectivity()
    if mode not in ("nvidia", "ollama"):
        with pytest.raises(agent_planner.PlannerUnavailable):
            agent_planner.request_agent_plan({})
    with pytest.raises(RuntimeError, match="selected provider"):
        agent_planner.generate_grounded_interpretation({})


def test_cli_unsupported_selection_preserves_analysis_without_using_baseten(monkeypatch, tmp_path):
    from pathlib import Path

    import analyze_dataset

    monkeypatch.setenv("LABLENS_AI_PROVIDER", "bluesminds")
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-baseten-fake")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **k: pytest.fail("wrong provider called"))
    source = Path(__file__).resolve().parents[1] / "data" / "sample_voltage_current.csv"
    result = analyze_dataset.analyze_csv(source, tmp_path, generate_ai=True)
    assert result["fit"]["success"]
    assert "Unsupported provider selection" in result["ai_note"]
    assert (tmp_path / "results.json").exists()


@pytest.mark.parametrize("mode", ["nvidia", "ollama", "baseten"])
def test_cli_routes_selected_provider_and_preserves_provenance(monkeypatch, tmp_path, mode):
    from pathlib import Path

    import analyze_dataset
    import hosted_model_provider
    import local_meta_provider

    monkeypatch.setenv("LABLENS_AI_PROVIDER", mode)
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-baseten-fake")
    calls = []

    def fake(context, titles=None, *, profile="legacy", **kwargs):
        calls.append((mode, kwargs))
        wrapper = ask_muse.generate_mock_report(context, titles, profile=profile)
        wrapper.update(source={"nvidia": "hosted_model", "ollama": "local_ollama", "baseten": "live_provider"}[mode],
                       model="test-model", is_mock=False, provider="test-provider")
        return wrapper

    def adapter(name):
        def invoke(*args, **kwargs):
            assert name == mode, "wrong provider adapter called"
            return fake(*args, **kwargs)
        return invoke

    monkeypatch.setattr(hosted_model_provider, "generate_interpretation", adapter("nvidia"))
    monkeypatch.setattr(local_meta_provider, "generate_scientific_report", adapter("ollama"))
    monkeypatch.setattr(ask_muse, "generate_interpretation", adapter("baseten"))
    source = Path(__file__).resolve().parents[1] / "data" / "sample_voltage_current.csv"
    result = analyze_dataset.analyze_csv(source, tmp_path, generate_ai=True)
    assert len(calls) == 1 and calls[0][0] == mode
    assert result["ai"]["source"] == {"nvidia": "hosted_model", "ollama": "local_ollama", "baseten": "live_provider"}[mode]
    assert not result["ai"]["is_mock"]
    if mode == "nvidia":
        assert calls[0][1]["confirmed"] is True
