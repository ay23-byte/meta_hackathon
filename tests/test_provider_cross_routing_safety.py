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
    with pytest.raises(agent_planner.PlannerUnavailable, match="selected provider"):
        agent_planner.request_agent_plan({})
    with pytest.raises(RuntimeError, match="selected provider"):
        agent_planner.generate_grounded_interpretation({})


def test_cli_nvidia_selection_preserves_analysis_without_using_baseten(monkeypatch, tmp_path):
    from pathlib import Path

    import analyze_dataset

    monkeypatch.setenv("LABLENS_AI_PROVIDER", "nvidia")
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-baseten-fake")
    monkeypatch.setattr(ask_muse, "generate_interpretation", lambda *a, **k: pytest.fail("wrong provider called"))
    source = Path(__file__).resolve().parents[1] / "data" / "sample_voltage_current.csv"
    result = analyze_dataset.analyze_csv(source, tmp_path, generate_ai=True)
    assert result["fit"]["success"]
    assert "selected provider is not yet supported" in result["ai_note"]
    assert (tmp_path / "results.json").exists()
