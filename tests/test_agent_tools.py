"""The tool registry is the only execution path; validation is strict."""

import inspect

import numpy as np
import pandas as pd
import pytest

import agent_tools
from agent_tools import (
    MAX_DEGREE,
    MAX_ROWS,
    TOOL_REGISTRY,
    ToolContext,
    ToolResult,
    execute_tool,
    registry_manifest,
    validate_tool_call,
)


@pytest.fixture
def ctx():
    frame = pd.DataFrame({
        "x": np.arange(10, dtype=float),
        "y": 2 * np.arange(10, dtype=float) + 1,
        "sigma": np.full(10, 0.5),
    })
    c = ToolContext(frame=frame, load_info={"duplicate_headers": []},
                    deadline=float("inf"))
    inspect_result = execute_tool("inspect_dataset", {}, c)
    assert inspect_result.ok, inspect_result.error
    return c


def test_registry_manifest_is_closed_and_descriptive():
    manifest = registry_manifest()
    assert len(manifest) == 10
    assert {item["tool"] for item in manifest} == set(TOOL_REGISTRY)
    assert all(item["description"] for item in manifest)
    assert MAX_ROWS == 50_000 and MAX_DEGREE == 4


def test_source_contains_no_dynamic_code_execution_primitives():
    source = inspect.getsource(agent_tools)
    for forbidden in ("eval(", "exec(", "compile(", "subprocess", "os.system", "pickle.loads"):
        assert forbidden not in source
    assert "__import__" not in source


@pytest.mark.parametrize("name", [
    "not_a_tool", "fit_curve.__class__", "__dict__", "eval", "exec", "os.system", "", None, 7,
])
def test_unknown_or_dangerous_tool_names_are_rejected(ctx, name):
    ok, _, reason = validate_tool_call(name, {}, ctx)
    assert not ok and "unknown tool" in reason


@pytest.mark.parametrize("params, expected", [
    ({"x": "x", "y": "y", "model": "linear", "extra": 1}, "unexpected"),
    ({"x": "x", "model": "linear"}, "missing"),
    ({"x": "x", "y": "y", "model": "linear", "degree": True}, "integer"),
    ({"x": "x", "y": "y", "model": "linear", "degree": 9}, "maximum"),
    ({"x": "x", "y": "y", "model": "quadratic"}, "must be one of"),
    ({"x": "missing_column", "y": "y", "model": "linear"}, "unknown column"),
    ({"x": "x", "y": "y", "model": "__import__('os')"}, "must be one of"),
])
def test_parameter_validation(ctx, params, expected):
    ok, _, reason = validate_tool_call("fit_curve", params, ctx)
    assert not ok and expected in (reason or "")


def test_plan_validation_rejects_unknown_models():
    from agent_planner import validate_plan

    bad = {
        "dataset_understanding": "test", "stop_condition": "test",
        "on_poor_fit": {"strategy": "halt_and_explain", "fallback_models": []},
        "steps": [{"tool": "fit_curve",
                   "params": {"x": "x", "y": "y", "model": "quadratic"},
                   "rationale": "test"}],
    }
    result = validate_plan(bad)
    assert not result.accepted
    assert any("unknown model" in reason for reason in result.reasons)


def test_destructive_tool_requires_explicit_user_confirmation(ctx):
    params = {"action": "remove_duplicate_rows"}
    ok, _, reason = validate_tool_call("request_confirmation", params, ctx)
    assert not ok and "confirmation" in reason
    ctx.user_confirmed = True
    ok, _, _ = validate_tool_call("request_confirmation", params, ctx)
    assert ok


def test_execute_tool_never_raises_on_bad_input(ctx):
    result = execute_tool("fit_curve", {"x": "x"}, ctx)
    assert isinstance(result, ToolResult) and not result.ok
    assert "validation rejected" in result.error


def test_fit_curve_numbers_match_the_deterministic_engine(ctx):
    from fitting_core import fit_model

    result = execute_tool("fit_curve", {"x": "x", "y": "y", "model": "linear"}, ctx)
    assert result.ok
    expected = fit_model("linear", ctx.x_values, ctx.y_values)
    assert result.result["parameters"]["slope"] == pytest.approx(expected.parameters["slope"])
    assert result.result["metrics"]["r2"] == pytest.approx(1.0)
    assert result.result["fit_ref"] == "fit_1"


def test_weighted_fit_uses_only_a_valid_uncertainty_column(ctx):
    result = execute_tool("fit_curve", {"x": "x", "y": "y", "model": "linear",
                                         "weights": "sigma"}, ctx)
    assert result.ok and result.result["weighted"] is True
    bad = execute_tool("fit_curve", {"x": "x", "y": "y", "model": "linear",
                                      "weights": "unknown"}, ctx)
    assert not bad.ok


def test_declare_insufficient_is_terminal_and_explicit(ctx):
    result = execute_tool("declare_insufficient", {"reason": "constant response"}, ctx)
    assert result.ok
    assert result.result["state"] == "INSUFFICIENT_EVIDENCE"


def test_inspect_dataset_counts_invalid_values_without_dropping_rows():
    frame = pd.DataFrame({"x": ["1", "2", "", "oops", "5"],
                          "y": ["2", "4", "6", "8", "NaN"]})
    c = ToolContext(frame=frame, load_info={"duplicate_headers": []},
                    deadline=float("inf"))
    result = execute_tool("inspect_dataset", {}, c)
    assert result.ok
    quality = result.result
    assert quality["rows"] == 5
    assert quality["missing"] >= 1 and quality["invalid"] >= 1
    assert quality["n_valid_pairs"] < quality["rows"]
    assert len(c.working) == 5  # no observation was removed
    assert "no values were imputed" in " ".join(quality["warnings"])


def test_tool_timeout_is_bounded(ctx):
    ctx.deadline = 0.0
    result = execute_tool("describe_statistics", {"columns": ["x"]}, ctx)
    assert not result.ok and "deadline" in result.error
