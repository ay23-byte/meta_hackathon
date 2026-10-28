"""Strict plan validation, offline fallback, provider seam and grounding."""

import json
import types

import pytest

import agent_planner as planner
import ask_muse
from agent_tools import registry_manifest


def quality():
    return {
        "rows": 20, "columns": ["x", "y"], "numeric_columns": ["x", "y"],
        "n_valid_pairs": 20, "duplicate_headers": [], "ambiguous_roles": False,
        "missing": 0, "invalid": 0, "nonfinite": 0, "invalid_ratio": {},
        "suggested_x": "x", "suggested_y": "y", "warnings": [],
    }


def custom_plan(*, steps=None, strategy="try_alternatives", fallbacks=None):
    steps = steps or [
        {"tool": "correlation_analysis",
         "params": {"x": "x", "y": "y", "method": "spearman"},
         "rationale": "rank association"},
        {"tool": "fit_curve", "params": {"x": "x", "y": "y", "model": "linear"},
         "rationale": "baseline"},
        {"tool": "diagnose_fit", "params": {"fit_ref": "fit_1"},
         "rationale": "check"},
    ]
    return {
        "dataset_understanding": "Two numeric columns.",
        "steps": steps,
        "on_poor_fit": {"strategy": strategy,
                        "fallback_models": ["polynomial"] if fallbacks is None else fallbacks},
        "stop_condition": "stop when diagnostics pass",
    }


def test_deterministic_plan_is_valid_and_schema_aware():
    plan = planner.deterministic_plan(quality())
    result = planner.validate_plan(plan)
    assert result.accepted, result.reasons
    tools = [step["tool"] for step in result.plan["steps"]]
    assert "fit_curve" in tools and "diagnose_fit" in tools
    assert "correlation_analysis" in tools


def test_plan_hash_is_stable_and_sensitive():
    a = planner.deterministic_plan(quality())
    b = json.loads(json.dumps(a))
    assert planner.plan_hash(a) == planner.plan_hash(b)
    b["steps"] = b["steps"][:-1]
    assert planner.plan_hash(a) != planner.plan_hash(b)


def test_plan_prompt_contains_allowlist_but_no_raw_rows():
    prompt = planner.build_plan_prompt(quality(), registry_manifest())
    for spec in registry_manifest():
        assert spec["tool"] in prompt
    assert "linear" in prompt and "pearson" in prompt
    assert "eval(" not in prompt


@pytest.mark.parametrize("mangle", [
    lambda p: p.update({"unexpected_key": 1}),
    lambda p: p.pop("stop_condition"),
    lambda p: p.update({"steps": []}),
    lambda p: p.update({"steps": p["steps"] * 4}),
    lambda p: p["steps"][0].update({"tool": "run_python_code"}),
    lambda p: p["steps"][0].update({"extra": 1}),
    lambda p: p["steps"].append(dict(p["steps"][0])),
    lambda p: p["on_poor_fit"].update({"strategy": "do_anything"}),
    lambda p: p["on_poor_fit"].update({"fallback_models": ["a", "b", "c", "d"]}),
    lambda p: p["steps"].append({"tool": "fit_curve",
                                  "params": {"x": "x", "y": "y", "model": "linear",
                                             "degree": 99},
                                  "rationale": "bad degree"}),
    lambda p: p.update({"dataset_understanding": "import os; eval('1')"}),
    lambda p: p["on_poor_fit"].update({"strategy": "halt_and_explain",
                                       "fallback_models": ["polynomial"]}),
])
def test_invalid_plans_are_rejected_before_any_execution(mangle):
    plan = custom_plan()
    mangle(plan)
    result = planner.validate_plan(plan)
    assert not result.accepted
    assert result.plan is None
    assert result.reasons


def test_unknown_model_and_method_are_rejected():
    plan = custom_plan(steps=[{"tool": "fit_curve",
                               "params": {"x": "x", "y": "y", "model": "neural_net"},
                               "rationale": "invalid model"}])
    result = planner.validate_plan(plan)
    assert not result.accepted
    plan = custom_plan(steps=[{"tool": "correlation_analysis",
                               "params": {"x": "x", "y": "y", "method": "kendall"},
                               "rationale": "invalid method"}])
    assert not planner.validate_plan(plan).accepted


def test_valid_alternative_plan_is_accepted_and_differs():
    first = planner.validate_plan(custom_plan())
    second = planner.validate_plan(custom_plan(steps=[
        {"tool": "outlier_scan", "params": {"column": "y"}, "rationale": "scan"},
        {"tool": "fit_curve", "params": {"x": "x", "y": "y", "model": "linear"},
         "rationale": "baseline"},
        {"tool": "diagnose_fit", "params": {"fit_ref": "fit_1"}, "rationale": "check"},
    ]))
    assert first.accepted and second.accepted
    assert [s["tool"] for s in first.plan["steps"]] != [s["tool"] for s in second.plan["steps"]]


def test_request_agent_plan_with_fake_provider(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    payload = json.dumps(custom_plan())
    response = types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content=payload))])
    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kwargs: object())
    monkeypatch.setattr(ask_muse, "_completion_request",
                        lambda client, prompt, **kwargs: response)
    raw = planner.request_agent_plan(quality(), registry_manifest())
    assert planner.validate_plan(raw).accepted


def test_request_agent_plan_without_key_or_with_bad_json(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    with pytest.raises(planner.PlannerUnavailable, match="not configured"):
        planner.request_agent_plan(quality())

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    response = types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content="not json at all"))])
    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kwargs: object())
    monkeypatch.setattr(ask_muse, "_completion_request",
                        lambda client, prompt, **kwargs: response)
    with pytest.raises(planner.PlannerUnavailable, match="invalid plan"):
        planner.request_agent_plan(quality())


def test_grounding_check_rejects_invented_numbers():
    results = [{"tool": "fit_curve", "result": {"metrics": {"r2": 0.987654}}}]
    assert planner.grounding_check("R2 is 0.987654.", results)["pass"]
    rejected = planner.grounding_check("Resistance is 42.123 ohms.", results)
    assert not rejected["pass"]
    assert 42.123 in rejected["unsupported_values"]


def test_deterministic_conclusion_uses_only_tool_numbers():
    digest = {
        "tool_results": [
            {"seq": 1, "tool": "fit_curve", "ok": True,
             "result": {"model": "linear", "n_observations": 20,
                        "equation": "y = 2*x + 1",
                        "metrics": {"r2": 0.999, "rmse": 0.01}}},
        ],
        "final": {"state": "DONE", "retries": []},
    }
    text = planner.deterministic_conclusion(digest)
    assert "0.999" in text and "20" in text and "linear" in text
    assert planner.grounding_check(text, digest["tool_results"])["pass"]


def test_deterministic_conclusion_for_insufficient_state_is_honest():
    digest = {"tool_results": [], "final": {"state": "INSUFFICIENT_EVIDENCE",
                                            "reasons": ["constant response"]}}
    text = planner.deterministic_conclusion(digest)
    assert "Insufficient evidence" in text
    assert "constant response" in text


def test_plan_budget_is_local_to_request(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    response = types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content=json.dumps(custom_plan())))])
    seen = []
    monkeypatch.setattr(ask_muse, "OpenAI", lambda **kwargs: object())

    def capture(client, prompt, **kwargs):
        seen.append((kwargs["max_tokens"], ask_muse.MAX_COMPLETION_TOKENS))
        return response

    monkeypatch.setattr(ask_muse, "_completion_request", capture)
    planner.request_agent_plan(quality(), registry_manifest())
    assert seen == [(planner.MAX_PLAN_TOKENS, ask_muse.MAX_COMPLETION_TOKENS)]
