"""Structured, exportable audit trail for every agent decision and tool call."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_tools import (
    MAX_FIT_ATTEMPTS,
    MAX_RETRIES,
    MAX_STEPS,
    MAX_TOOL_S,
    MAX_WALL_S,
    ToolResult,
)


@dataclass
class AgentEvent:
    seq: int
    phase: str
    actor: str                 # "ai" | "deterministic" | "user"
    tool: str | None
    params: dict
    status: str
    duration_ms: float
    result_digest: dict
    decision: str
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "seq": self.seq, "phase": self.phase, "actor": self.actor,
            "tool": self.tool, "params": self.params, "status": self.status,
            "duration_ms": round(self.duration_ms, 3),
            "result_digest": self.result_digest, "decision": self.decision,
            "warnings": self.warnings,
        }


class AgentRun:
    """One complete, bounded agent run."""

    def __init__(self, *, dataset: dict, limits: dict | None = None):
        self.run_id = "agent-" + hashlib.sha256(
            f"{time.time_ns()}-{dataset.get('name', '')}".encode()
        ).hexdigest()[:12]
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.started_monotonic = time.monotonic()
        self.dataset = dataset
        self.limits = limits or {
            "max_steps": MAX_STEPS, "max_retries": MAX_RETRIES,
            "max_fit_attempts": MAX_FIT_ATTEMPTS, "max_tool_s": MAX_TOOL_S,
            "max_wall_s": MAX_WALL_S,
        }
        self.plan_source = "not_requested"
        self.plan_hash = ""
        self.quality_summary: dict = {}
        self.plan_validation: dict = {}
        self.events: list[AgentEvent] = []
        self.retries: list[dict] = []
        self.final: dict = {}
        self.tool_results: list[dict] = []
        self.decisions: list[dict] = []

    # -- recording ---------------------------------------------------------
    def log(self, *, phase: str, actor: str, tool: str | None = None,
            params: dict | None = None, status: str = "ok",
            duration_ms: float = 0.0, result_digest: dict | None = None,
            decision: str = "", warnings: list[str] | None = None) -> int:
        seq = len(self.events) + 1
        event = AgentEvent(
            seq=seq, phase=phase, actor=actor, tool=tool,
            params=params or {}, status=status, duration_ms=duration_ms,
            result_digest=result_digest or {}, decision=decision,
            warnings=list(warnings or []),
        )
        self.events.append(event)
        if tool is not None and actor == "deterministic":
            self.tool_results.append({
                "seq": seq, "tool": tool, "ok": status == "ok",
                "result": event.result_digest,
            })
        if decision:
            self.decisions.append({"seq": seq, "phase": phase, "decision": decision})
        return seq

    def log_tool(self, result: ToolResult, *, phase: str = "execute",
                 decision: str = "") -> int:
        return self.log(
            phase=phase, actor="deterministic", tool=result.tool,
            params=result.params, status="ok" if result.ok else "error",
            duration_ms=result.duration_ms,
            result_digest=result.result if result.ok else {"error": result.error},
            decision=decision, warnings=result.warnings,
        )

    def finalize(self, *, state: str, conclusion: str,
                 evidence_refs: list[int] | None = None,
                 reasons: list[str] | None = None,
                 ai_report: dict | None = None) -> None:
        self.final = {
            "state": state,
            "conclusion": conclusion,
            "evidence_refs": evidence_refs or [],
            "insufficient_evidence": state != "DONE",
            "reasons": reasons or [],
            "retries": list(self.retries),
            "ai_report": ai_report,
            "grounding_check": (ai_report or {}).get("grounding_check"),
            "wall_ms": round((time.monotonic() - self.started_monotonic) * 1000, 2),
        }
        self.log(phase="final", actor="deterministic", status="ok",
                 result_digest={"state": state, "evidence_refs": self.final["evidence_refs"]},
                 decision=f"terminal state {state}")

    # -- exports -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "started_at": self.started_at,
            "plan_source": self.plan_source,
            "plan_hash": self.plan_hash,
            "dataset": self.dataset,
            "limits": self.limits,
            "quality_summary": self.quality_summary,
            "plan_validation": self.plan_validation,
            "events": [event.as_dict() for event in self.events],
            "retries": self.retries,
            "tool_results": self.tool_results,
            "decisions": self.decisions,
            "final": self.final,
            "totals": {
                "events": len(self.events),
                "steps": sum(1 for e in self.events if e.phase == "execute"),
                "retries": len(self.retries),
                "tools_called": {
                    tool: sum(1 for e in self.events if e.tool == tool)
                    for tool in sorted({e.tool for e in self.events if e.tool})
                },
            },
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2,
                          allow_nan=False, default=str).encode("utf-8")

    def to_jsonl(self) -> bytes:
        return ("\n".join(json.dumps(event.as_dict(), ensure_ascii=False,
                                    allow_nan=False, default=str)
                          for event in self.events) + "\n").encode("utf-8")

    def mermaid(self) -> str:
        lines = ["flowchart TD"]
        for event in self.events:
            label = event.tool or event.phase
            decision = event.decision.replace('"', "'")[:48]
            lines.append(f'  E{event.seq}["{event.seq} {event.actor}: {label}<br/>{decision}"]')
        for first, second in zip(self.events, self.events[1:], strict=False):
            lines.append(f"  E{first.seq} --> E{second.seq}")
        return "\n".join(lines)

    def to_markdown(self) -> str:
        data = self.to_dict()
        lines = [
            "# LabLens analysis agent audit trail", "",
            f"- Run ID: `{data['run_id']}`",
            f"- Started (UTC): {data['started_at']}",
            f"- Plan source: **{data['plan_source']}**",
            f"- Plan hash: `{data['plan_hash']}`",
            f"- Dataset: `{data['dataset'].get('name')}` "
            f"({data['dataset'].get('rows')} rows, sha256 `{str(data['dataset'].get('sha256'))[:16]}...`)",
            f"- Limits: {json.dumps(data['limits'])}",
            "", "## Data-quality summary", "",
            "```json", json.dumps(data["quality_summary"], ensure_ascii=False, indent=2, default=str), "```",
            "", "## Plan validation", "",
            "```json", json.dumps(data["plan_validation"], ensure_ascii=False, indent=2, default=str), "```",
            "", "## Execution log", "",
            "| # | Phase | Actor | Tool | Status | ms | Decision |",
            "| ---: | --- | --- | --- | --- | ---: | --- |",
        ]
        for event in data["events"]:
            lines.append(
                f"| {event['seq']} | {event['phase']} | {event['actor']} | "
                f"{event['tool'] or '-'} | {event['status']} | "
                f"{event['duration_ms']:.1f} | {event['decision'].replace('|', '/')} |"
            )
        lines += ["", "## Retries", ""]
        if data["retries"]:
            for retry in data["retries"]:
                lines.append(f"- {json.dumps(retry, ensure_ascii=False, default=str)}")
        else:
            lines.append("- None.")
        final = data["final"]
        lines += [
            "", "## Final interpretation", "",
            f"- State: **{final.get('state')}**",
            f"- Insufficient evidence: {final.get('insufficient_evidence')}",
            f"- Evidence refs: {final.get('evidence_refs')}",
            "",
            final.get("conclusion", ""), "",
        ]
        if final.get("ai_report") and not final["ai_report"].get("rejected"):
            lines += ["### AI-generated sections (unverified hypotheses)", ""]
            for section in final["ai_report"]["structured"]["sections"]:
                lines += [f"**{section['title']}**: {section['content']}", ""]
        lines += ["", "## Timeline", "", "```mermaid", self.mermaid(), "```", ""]
        return "\n".join(lines)

    def digest_for_ai(self) -> dict:
        """Only executed tool outputs and decisions; no raw rows, no prior AI text."""
        return {
            "dataset": self.dataset,
            "quality_summary": self.quality_summary,
            "tool_results": self.tool_results,
            "decisions": self.decisions,
            "final": {"state": self.final.get("state")},
        }
