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
    assert len(manifest) == len(TOOL_REGISTRY) == 13
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


def test_compare_models_and_evidence_summary_use_only_computed_fits(ctx):
    fit = execute_tool("fit_curve", {"x": "x", "y": "y", "model": "linear"}, ctx)
    assert fit.ok
    comparison = execute_tool(
        "compare_models", {"x": "x", "y": "y", "models": ["linear", "polynomial"]}, ctx
    )
    assert comparison.ok, comparison.error
    rows = comparison.result["comparison"]
    assert len(rows) == 2 and all(row["success"] for row in rows)
    assert any(row["r2"] == pytest.approx(1.0) for row in rows)
    assert comparison.result["n_observations"] == 10

    summary = execute_tool("evidence_summary", {}, ctx)
    assert summary.ok
    assert summary.result["n_fits"] == 1
    assert summary.result["evidence"][0]["result_id"].startswith("fit.fit_")
    assert summary.result["n_valid_pairs"] == 10

    bad = execute_tool("compare_models",
                       {"x": "x", "y": "y", "models": ["not_a_model"]}, ctx)
    assert not bad.ok and "must contain only" in bad.error


def test_time_series_summary_is_descriptive_and_bounded(ctx):
    result = execute_tool("time_series_summary",
                          {"time": "x", "value": "y", "max_lag": 2}, ctx)
    assert result.ok, result.error
    assert result.result["n_points"] == 10
    assert result.result["mean_step"] == pytest.approx(2.0)
    assert result.result["lag_correlations"]["1"]["coefficient"] == pytest.approx(1.0)
    assert set(result.result["lag_correlations"]) == {"1", "2"}
    assert "no forecasting" in result.result["note"]

    bad = execute_tool("time_series_summary",
                       {"time": "x", "value": "y", "max_lag": 9}, ctx)
    assert not bad.ok and "maximum" in bad.error


def test_timed_out_tool_cannot_mutate_audited_context(monkeypatch, ctx):
    import time

    import agent_tools

    def slow_tool(worker_ctx, params):
        time.sleep(0.1)
        worker_ctx.roles["x"] = "late mutation"
        return {"ok": True}

    monkeypatch.setattr(agent_tools, "MAX_TOOL_S", 0.01)
    monkeypatch.setitem(agent_tools.TOOL_REGISTRY, "slow_test", agent_tools.ToolSpec("slow_test", slow_tool, {}))
    ctx.deadline = time.monotonic() + 1
    original_roles = dict(ctx.roles)
    result = agent_tools.execute_tool("slow_test", {}, ctx)
    assert not result.ok and "budget" in result.error
    assert not agent_tools.execute_tool("slow_test", {}, ctx).ok
    time.sleep(0.15)  # The timed-out worker has completed on its isolated copy.
    assert ctx.roles == original_roles


def test_tool_exception_redacts_configured_secret(monkeypatch, ctx):
    import time

    import agent_tools

    secret = "unit-test-sensitive-value"
    monkeypatch.setenv("BASETEN_API_KEY", secret)
    def failing_tool(worker_ctx, params):
        raise ValueError(secret)
    monkeypatch.setitem(agent_tools.TOOL_REGISTRY, "fail_test", agent_tools.ToolSpec("fail_test", failing_tool, {}))
    ctx.deadline = time.monotonic() + 1
    result = agent_tools.execute_tool("fail_test", {}, ctx)
    assert not result.ok and secret not in result.error and "[redacted]" in result.error


def test_weighted_fit_aligns_uncertainties_to_the_selected_axes():
    frame = pd.DataFrame({"x": [0., 1., 2., 3., 4.],
                          "y": [1., float("nan"), 5., 7., 9.],
                          "other": [float("nan"), 3., 5., 7., 9.],
                          "sigma": [0.1, 0.2, 0.3, 0.4, 0.5]})
    c = ToolContext(frame=frame, load_info={}, deadline=float("inf"), working=frame,
                    pair_mask=np.array([True, False, True, True, True]),
                    x_values=np.array([0., 2., 3., 4.]))
    result = execute_tool("fit_curve", {"x": "x", "y": "other", "model": "linear", "weights": "sigma"}, c)
    assert result.ok, result.error
    assert result.result["weighted"] is True
    assert result.result["parameters"]["slope"] == pytest.approx(2.0)
    assert c.fits[result.result["fit_ref"]].n_observations == 4


def test_weighted_fit_rejects_unrepresentable_inverse_variances(ctx):
    ctx.working["sigma"] = 1e-200
    result = execute_tool("fit_curve", {"x": "x", "y": "y", "model": "linear", "weights": "sigma"}, ctx)
    assert not result.ok and "numerical range" in result.error
