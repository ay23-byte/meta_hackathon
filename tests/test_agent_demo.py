"""The A-E demo is reproducible offline and writes real audit artifacts."""

import json

import pytest

import run_agent_demo


def test_list_cases_prints_expected_behaviour(capsys):
    assert run_agent_demo.main(["--list"]) == 0
    output = capsys.readouterr().out
    for case_id, case in run_agent_demo.CASES.items():
        assert case_id in output
        assert case["expected_state"] in output


@pytest.mark.parametrize("case_id", list(run_agent_demo.CASES))
def test_each_case_writes_audit_artifacts_and_expected_state(tmp_path, case_id):
    assert run_agent_demo.main(["--case", case_id, "--strict",
                                "--output-dir", str(tmp_path)]) == 0
    destination = tmp_path / case_id
    for name in ("agent_audit.json", "agent_events.jsonl", "agent_report.md"):
        assert (destination / name).is_file(), name
    data = json.loads((destination / "agent_audit.json").read_text(encoding="utf-8"))
    assert data["final"]["state"] == run_agent_demo.CASES[case_id]["expected_state"]
    assert data["events"]
    assert case_id in ("c_ambiguous", "d") or data["plan_validation"].get("accepted")
    jsonl = (destination / "agent_events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(jsonl) == len(data["events"])
    assert "```mermaid" in (destination / "agent_report.md").read_text(encoding="utf-8")


def test_all_cases_in_strict_mode(tmp_path, capsys):
    assert run_agent_demo.main(["--case", "all", "--strict",
                                "--output-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert output.count("OK") >= len(run_agent_demo.CASES)
    assert all((tmp_path / key / "agent_audit.json").is_file()
               for key in run_agent_demo.CASES)


def test_ai_flag_without_key_falls_back_to_offline(capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    assert run_agent_demo.main(["--case", "a", "--use-ai", "--strict",
                                "--output-dir", str(tmp_path)]) == 0
    assert "BASETEN_API_KEY is unset" in capsys.readouterr().err
    data = json.loads((tmp_path / "a" / "agent_audit.json").read_text(encoding="utf-8"))
    assert data["plan_source"] == "deterministic_fallback"


def test_agent_cli_flag_writes_audit_next_to_standard_artifacts(tmp_path, capsys):
    import analyze_dataset

    csv = run_agent_demo.EXAMPLES / "case_a_linear.csv"
    assert analyze_dataset.main([str(csv), "--agent", "--output-dir", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert "Agent state: DONE" in printed
    assert (tmp_path / "agent" / "agent_audit.json").is_file()
    assert (tmp_path / "results.json").is_file()
