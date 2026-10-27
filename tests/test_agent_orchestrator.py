"""End-to-end agent workflow: three demo cases, retries, and AI plan influence."""

from pathlib import Path

import pytest

import agent_planner as planner
from agent_core import AnalysisOrchestrator, OrchestratorConfig
from data_io import read_csv_robust

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "agent_examples"


def load(name):
    path = EXAMPLES / name
    return read_csv_robust(path, source_name=path.name)


def run(name, **kwargs):
    config = OrchestratorConfig(use_ai=False, **kwargs)
    return AnalysisOrchestrator(config).run(load(name)).to_dict()


def tools(data, phase=None):
    return [event["tool"] for event in data["events"]
            if event["tool"] and (phase is None or event["phase"] == phase)]


def test_case_a_supported_conclusion_without_retry():
    data = run("case_a_linear.csv")
    assert data["final"]["state"] == "DONE"
    assert data["totals"]["retries"] == 0
    assert data["plan_source"] == "deterministic_fallback"
    assert data["plan_validation"]["accepted"] is True
    assert tools(data).count("fit_curve") == 1
    assert "diagnose_fit" in tools(data)
    assert "R2" in data["final"]["conclusion"]
    assert all(ref in {e["seq"] for e in data["events"]}
               for ref in data["final"]["evidence_refs"])


def test_case_b_retries_with_a_validated_alternative():
    data = run("case_b_curved.csv")
    assert data["final"]["state"] == "DONE"
    assert data["totals"]["retries"] == 1
    assert tools(data).count("fit_curve") == 2
    assert data["retries"][0]["to"] == "polynomial"
    fits = [e for e in data["events"] if e["tool"] == "fit_curve" and e["status"] == "ok"]
    assert fits[0]["params"]["model"] == "linear"
    assert fits[1]["params"]["model"] == "polynomial"
    assert "polynomial" in data["final"]["conclusion"]


def test_case_b_prime_halts_without_inventing_a_conclusion():
    data = run("case_b_unsalvageable.csv")
    assert data["final"]["state"] == "INSUFFICIENT_EVIDENCE"
    assert data["final"]["insufficient_evidence"] is True
    check = planner.grounding_check(data["final"]["conclusion"], data["tool_results"])
    assert check["pass"]


def test_case_c_recovers_from_invalid_values_without_deleting_rows():
    data = run("case_c_messy.csv")
    assert data["final"]["state"] == "DONE"
    quality = data["quality_summary"]
    assert quality["rows"] == 9
    assert quality["n_valid_pairs"] == 6
    assert quality["missing"] == 1 and quality["invalid"] == 1 and quality["nonfinite"] == 1
    assert any(event["phase"] == "recovery" for event in data["events"])
    assert any("no values were imputed" in warning
               for warning in data["events"][0]["result_digest"]["warnings"])


def test_case_c_ambiguous_requests_clarification_before_any_fit():
    data = run("case_c_ambiguous.csv")
    assert data["final"]["state"] == "NEEDS_CLARIFICATION"
    assert "Duplicate header" in data["final"]["conclusion"]
    assert "fit_curve" not in tools(data)


def ai_plan(*, first_tool="outlier_scan", strategy="try_alternatives", fallbacks=None):
    steps = []
    if first_tool:
        steps.append({"tool": first_tool, "params": {"column": "y"} if first_tool == "outlier_scan" else {},
                      "rationale": "inspect data"})
    steps += [
        {"tool": "fit_curve", "params": {"x": "x", "y": "y", "model": "linear"},
         "rationale": "baseline model"},
        {"tool": "diagnose_fit", "params": {"fit_ref": "fit_1"}, "rationale": "check"},
    ]
    return {
        "dataset_understanding": "AI-selected tools.",
        "steps": steps,
        "on_poor_fit": {"strategy": strategy,
                        "fallback_models": ["polynomial"] if fallbacks is None else fallbacks},
        "stop_condition": "stop on pass or exhaustion",
    }


def test_two_different_valid_ai_plans_produce_different_tool_sequences():
    # Build a frame whose columns are literally x/y so the AI plan params match.
    import numpy as np
    import pandas as pd

    frame = pd.DataFrame({"x": np.linspace(0, 5, 20),
                          "y": 2 * np.linspace(0, 5, 20) + 1})
    load_obj = read_csv_robust(
        frame.to_csv(index=False).encode("utf-8"), source_name="x_y.csv"
    )

    def with_plan(plan):
        config = OrchestratorConfig(use_ai=True, plan_provider=lambda quality: plan)
        return AnalysisOrchestrator(config).run(load_obj).to_dict()

    first = with_plan(ai_plan(first_tool="outlier_scan"))
    second = with_plan(ai_plan(first_tool="profile_columns"))
    assert first["plan_source"] == second["plan_source"] == "muse_spark"
    assert first["plan_hash"] != second["plan_hash"]
    assert "outlier_scan" in tools(first) and "outlier_scan" not in tools(second)
    assert "profile_columns" in tools(second) and "profile_columns" not in tools(first)
    assert any(event["actor"] == "ai" and event["phase"] == "plan"
               for event in first["events"])


def test_rejected_ai_plan_never_executes_its_tools():
    bad = ai_plan()
    bad["steps"].insert(0, {"tool": "run_arbitrary_python", "params": {},
                             "rationale": "should never run"})
    config = OrchestratorConfig(use_ai=True, plan_provider=lambda quality: bad)
    data = AnalysisOrchestrator(config).run(load("case_a_linear.csv")).to_dict()
    assert data["plan_source"] == "deterministic_fallback_after_rejection"
    assert data["plan_validation"]["accepted"] is True
    assert any(event["status"] == "rejected" and event["phase"] == "validate"
               for event in data["events"])
    assert "run_arbitrary_python" not in tools(data)


def test_halt_and_explain_plan_suppresses_retries():
    config = OrchestratorConfig(
        use_ai=True,
        plan_provider=lambda quality: ai_plan(strategy="halt_and_explain", fallbacks=[]),
    )
    # Use the x/y-shaped frame so the AI plan's column names resolve.
    import numpy as np
    import pandas as pd

    xv = np.linspace(-4, 4, 25)
    frame = pd.DataFrame({"x": xv, "y": 1.5 - 0.7 * xv + 0.35 * xv**2})
    load_obj = read_csv_robust(frame.to_csv(index=False).encode("utf-8"),
                               source_name="curved.csv")
    data = AnalysisOrchestrator(config).run(load_obj).to_dict()
    assert data["final"]["state"] == "INSUFFICIENT_EVIDENCE"
    assert data["totals"]["retries"] == 0
    assert any("halting" in reason.lower() for reason in data["final"]["reasons"])


def test_retry_budget_is_enforced():
    data = run("case_b_curved.csv", max_retries=0)
    assert data["totals"]["retries"] == 0
    assert data["final"]["state"] == "INSUFFICIENT_EVIDENCE"


def test_global_deadline_halts_cleanly():
    # Use a deadline already in the past: time.monotonic() resolution on
    # Windows is ~15 ms, so max_wall_s=0 can be flaky there.
    data = run("case_a_linear.csv", max_wall_s=-1)
    assert data["final"]["state"] == "FAILED"
    assert data["final"]["conclusion"]


def test_destructive_tool_requires_user_confirmation():
    plan = ai_plan(first_tool=None)
    plan["steps"].insert(0, {"tool": "request_confirmation",
                             "params": {"action": "remove_duplicate_rows"},
                             "rationale": "ask first"})
    config = OrchestratorConfig(use_ai=True, plan_provider=lambda quality: plan,
                                user_confirmed=False)
    import numpy as np
    import pandas as pd

    frame = pd.DataFrame({"x": np.arange(10.0), "y": 2 * np.arange(10.0)})
    load_obj = read_csv_robust(frame.to_csv(index=False).encode("utf-8"),
                               source_name="x_y.csv")
    data = AnalysisOrchestrator(config).run(load_obj).to_dict()
    confirmations = [e for e in data["events"] if e["tool"] == "request_confirmation"]
    assert confirmations and confirmations[0]["status"] == "error"

    config.user_confirmed = True
    allowed = AnalysisOrchestrator(config).run(load_obj).to_dict()
    confirmations = [e for e in allowed["events"] if e["tool"] == "request_confirmation"]
    assert confirmations and confirmations[0]["status"] == "ok"


def test_plan_provider_failure_falls_back_safely():
    def failing(quality):
        raise RuntimeError("provider down")

    config = OrchestratorConfig(use_ai=True, plan_provider=failing)
    data = AnalysisOrchestrator(config).run(load("case_a_linear.csv")).to_dict()
    assert data["plan_source"] == "deterministic_fallback"
    assert data["final"]["state"] == "DONE"


def test_ai_interpretation_rejected_by_grounding_is_not_used():
    config = OrchestratorConfig(
        use_ai=True,
        plan_provider=lambda quality: planner.deterministic_plan(quality),
        interpretation_provider=lambda digest: {"rejected": True,
                                                "grounding_check": {"pass": False}},
    )
    data = AnalysisOrchestrator(config).run(load("case_a_linear.csv")).to_dict()
    assert any(e["phase"] == "interpret" and e["status"] == "rejected"
               for e in data["events"])
    assert data["final"]["conclusion"].startswith("Executed tools")


def test_numerical_outputs_equal_direct_deterministic_calls():
    from fitting_core import fit_model

    data = run("case_a_linear.csv")
    fit_event = next(e for e in data["events"] if e["tool"] == "fit_curve")
    expected = fit_model("linear", load("case_a_linear.csv").frame["t_s"],
                         load("case_a_linear.csv").frame["signal_mV"])
    assert fit_event["result_digest"]["parameters"]["slope"] == pytest.approx(
        expected.parameters["slope"]
    )
