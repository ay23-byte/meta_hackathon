"""Reproducible three-case demonstration of the analysis agent.

Runs entirely offline by default (deterministic fallback planner). With
BASETEN_API_KEY set, pass --use-ai to let Muse Spark propose the plan and the
final interpretation; both still go through strict validation.

    python run_agent_demo.py --case all --output-dir outputs/agent_demo
    python run_agent_demo.py --case b --use-ai
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent_core import AnalysisOrchestrator, OrchestratorConfig
from data_io import read_csv_robust

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "data" / "agent_examples"
DEFAULT_OUTPUT = ROOT / "outputs" / "agent_demo"

CASES = {
    "a": {
        "file": "case_a_linear.csv",
        "title": "A - clean linear data",
        "expected_state": "DONE",
        "expected_behaviour": "Plan validates, linear fit passes diagnostics, no retry, supported conclusion.",
    },
    "b": {
        "file": "case_b_curved.csv",
        "title": "B - poor initial model",
        "expected_state": "DONE",
        "expected_behaviour": "Linear fit fails residual/R2 diagnostics; validated polynomial alternative is fitted and accepted.",
    },
    "b_fail": {
        "file": "case_b_unsalvageable.csv",
        "title": "B' - no justifiable model",
        "expected_state": "INSUFFICIENT_EVIDENCE",
        "expected_behaviour": "Constant response makes R2 undefined; agent stops without inventing a conclusion.",
    },
    "c": {
        "file": "case_c_messy.csv",
        "title": "C - missing/invalid recovery",
        "expected_state": "DONE",
        "expected_behaviour": "Invalid, missing and inf values are detected; pairwise-complete recovery keeps all original rows.",
    },
    "c_ambiguous": {
        "file": "case_c_ambiguous.csv",
        "title": "C' - ambiguous schema",
        "expected_state": "NEEDS_CLARIFICATION",
        "expected_behaviour": "Duplicate header names force a clarification request before any fitting.",
    },
}


def run_case(case_id: str, output_dir: Path, *, use_ai: bool = False,
             user_confirmed: bool = False):
    """Execute one case, print an actor-labelled trace, and write audit files."""
    case = CASES[case_id]
    path = EXAMPLES / case["file"]
    load = read_csv_robust(path, source_name=path.name)
    config = OrchestratorConfig(use_ai=use_ai, user_confirmed=user_confirmed)
    run = AnalysisOrchestrator(config).run(load)

    destination = output_dir / case_id
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "agent_audit.json").write_bytes(run.to_json_bytes())
    (destination / "agent_events.jsonl").write_bytes(run.to_jsonl())
    (destination / "agent_report.md").write_text(run.to_markdown(), encoding="utf-8")

    data = run.to_dict()
    print(f"\n=== {case['title']} [{case_id}] ===")
    print(f"file: {path.name} | rows: {data['dataset']['rows']} | "
          f"plan source: {data['plan_source']}")
    print(f"expected: {case['expected_behaviour']}")
    print("-" * 108)
    print(f"{'#':>3}  {'ACTOR':<15} {'PHASE':<12} {'TOOL':<22} {'STATUS':<9} DECISION")
    for event in data["events"]:
        actor = ("AI DECISION" if event["actor"] == "ai" else "DETERMINISTIC TOOL"
                 if event["tool"] else "DETERMINISTIC POLICY")
        print(f"{event['seq']:>3}  {actor:<15} {event['phase']:<12} "
              f"{event['tool'] or '-'!s:<22} {event['status']:<9} {event['decision'][:70]}")
    print("-" * 108)
    print(f"quality: {json.dumps({k: data['quality_summary'].get(k) for k in ('rows','n_valid_pairs','missing','invalid','nonfinite','duplicate_headers')})}")
    print(f"plan validation: {json.dumps({k: data['plan_validation'].get(k) for k in ('accepted','reasons')})}")
    print(f"retries: {json.dumps(data['retries'])}")
    print(f"FINAL STATE: {data['final']['state']}")
    print(f"CONCLUSION: {data['final']['conclusion']}")
    print(f"artifacts: {destination}")
    return run


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="all", choices=[*CASES, "all"])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--use-ai", action="store_true",
                        help="Let Muse Spark propose the plan (needs BASETEN_API_KEY).")
    parser.add_argument("--user-confirmed", action="store_true",
                        help="Grant explicit confirmation for destructive tools.")
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero if a case's observed state differs from the expected state.")
    parser.add_argument("--list", action="store_true", help="List cases and exit.")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        for key, case in CASES.items():
            print(f"{key:12s} {case['title']:32s} -> {case['expected_state']}")
            print(f"             {case['expected_behaviour']}")
        return 0
    use_ai = bool(args.use_ai and os.getenv("BASETEN_API_KEY", "").strip())
    if args.use_ai and not use_ai:
        print("Note: --use-ai requested but BASETEN_API_KEY is unset; using the offline planner.",
              file=sys.stderr)
    ids = list(CASES) if args.case == "all" else [args.case]
    results = {}
    for case_id in ids:
        run = run_case(case_id, Path(args.output_dir), use_ai=use_ai,
                       user_confirmed=args.user_confirmed)
        results[case_id] = run.to_dict()["final"]["state"]
    print("\n=== summary ===")
    for case_id, state in results.items():
        expected = CASES[case_id]["expected_state"]
        flag = "OK" if state == expected else "UNEXPECTED"
        print(f"{case_id:12s} expected={expected:24s} observed={state:24s} {flag}")
    if args.strict and any(state != CASES[key]["expected_state"]
                           for key, state in results.items()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
