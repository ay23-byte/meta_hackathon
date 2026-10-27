"""The audit trail is complete, strict JSON, and cites real evidence."""

import json

from agent_audit import AgentRun
from agent_tools import ToolResult


def build_run():
    run = AgentRun(dataset={"name": "a.csv", "sha256": "a" * 64, "rows": 20, "columns": ["x", "y"]})
    run.plan_source = "muse_spark"
    run.plan_hash = "sha256:abc"
    run.quality_summary = {"n_valid_pairs": 20, "invalid": 0}
    run.plan_validation = {"accepted": True, "reasons": []}
    run.log_tool(ToolResult(True, "fit_curve", {"model": "linear"}, 2.0,
                            result={"metrics": {"r2": 0.999}}),
                 phase="execute", decision="AI-selected tool")
    run.log(phase="retry", actor="ai", status="ok",
            result_digest={"alternative": "polynomial"},
            decision="validated plan alternative selected")
    run.retries.append({"attempt": 1, "from": "linear", "to": "polynomial"})
    run.finalize(state="DONE", conclusion="R2 = 0.999.", evidence_refs=[1],
                 ai_report=None)
    return run


def test_audit_json_is_strict_and_complete():
    run = build_run()
    payload = run.to_json_bytes()
    data = json.loads(payload)
    assert b"NaN" not in payload and b"Infinity" not in payload
    for key in ("schema_version", "run_id", "plan_source", "plan_hash", "dataset",
                "limits", "quality_summary", "plan_validation", "events",
                "retries", "tool_results", "decisions", "final", "totals"):
        assert key in data
    assert data["final"]["state"] == "DONE"
    assert data["totals"]["tools_called"]["fit_curve"] == 1


def test_jsonl_has_one_line_per_event():
    run = build_run()
    lines = run.to_jsonl().decode("utf-8").strip().splitlines()
    assert len(lines) == len(run.events) == run.to_dict()["totals"]["events"]
    for index, line in enumerate(lines, start=1):
        assert json.loads(line)["seq"] == index


def test_markdown_contains_decisions_and_mermaid():
    text = build_run().to_markdown()
    for heading in ("Data-quality summary", "Plan validation", "Execution log",
                    "Retries", "Final interpretation", "Timeline"):
        assert heading in text
    assert "AI-selected tool" in text
    assert "```mermaid" in text
    assert "E1 --> E2" in text


def test_evidence_refs_point_to_real_events():
    run = build_run()
    seqs = {event.seq for event in run.events}
    assert all(ref in seqs for ref in run.final["evidence_refs"])


def test_ai_digest_excludes_raw_rows_and_prior_ai_text():
    run = build_run()
    run.final["ai_report"] = {"structured": {"sections": [{"title": "x",
                                                            "content": "secret 12345"}]}}
    digest = run.digest_for_ai()
    blob = json.dumps(digest)
    assert "12345" not in blob
    assert "secret" not in blob
    assert "tool_results" in digest


def test_mermaid_timeline_is_well_formed():
    mermaid = build_run().mermaid()
    assert mermaid.startswith("flowchart TD")
    assert all(f"E{event.seq}" in mermaid for event in build_run().events)
