"""Validated tool registry: the ONLY execution path available to the agent.

No model-supplied text is ever interpreted as Python. Every call is looked up
by an exact registry key, its parameters are checked against a declarative
specification, and the wrapped function is one of this repository's pure
deterministic helpers. Numerical results therefore always come from Python.
"""

from __future__ import annotations

import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import provider_config
from cleaning import apply_cleaning, build_plan, paired_values
from column_inference import infer_columns, suggest_roles
from data_io import coerce_numeric
from fitting_core import MODEL_SPECS, fit_model, inverse_variance_weights
from fitting_core import compare_models as rank_models
from statistics_core import correlation, covariance, describe_numeric, outlier_diagnostics
from visualization_core import PLOT_TYPES, build_chart

# Hard bounds. These are deliberately stricter than the interactive app.
MAX_TOOL_S = 5.0
MAX_WALL_S = 30.0
MAX_STEPS = 8
MAX_RETRIES = 2
MAX_FIT_ATTEMPTS = 3
MAX_ROWS = 50_000
MAX_COLUMNS = 20
MAX_STATS_COLUMNS = 10
MAX_DEGREE = 4
MAX_FALLBACK_MODELS = 3

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lablens-agent")


@dataclass(frozen=True)
class ParamSpec:
    kind: str                       # str | int | bool | list[str] | optional_str
    required: bool = True
    choices: tuple = ()
    minimum: float | None = None
    maximum: float | None = None
    column: bool = False            # must name a column of the working frame


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: object
    params: dict
    side_effect: str = "read_only"  # read_only | destructive | terminal
    description: str = ""


@dataclass
class ToolResult:
    ok: bool
    tool: str
    params: dict
    duration_ms: float
    result: dict = field(default_factory=dict)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "tool": self.tool, "params": self.params,
            "duration_ms": round(self.duration_ms, 3), "result": self.result,
            "error": self.error, "warnings": self.warnings,
        }


@dataclass
class ToolContext:
    """Mutable state shared by the validated tools during one run."""

    frame: pd.DataFrame
    load_info: dict
    deadline: float
    user_confirmed: bool = False
    profiles: list = field(default_factory=list)
    roles: dict = field(default_factory=dict)
    cleaning: object = None
    working: pd.DataFrame | None = None
    x_values: np.ndarray | None = None
    y_values: np.ndarray | None = None
    pair_mask: np.ndarray | None = None
    fits: dict = field(default_factory=dict)
    quality: dict = field(default_factory=dict)
    fit_counter: int = 0


def _validate_scalar(name: str, value, spec: ParamSpec, ctx: ToolContext):
    if spec.kind == "optional_str" and value is None:
        return None
    if spec.kind in ("str", "optional_str"):
        if not isinstance(value, str) or not value.strip():
            return f"parameter '{name}' must be a non-empty string"
        if len(value) > 120:
            return f"parameter '{name}' is too long"
        if spec.choices and value not in spec.choices:
            return f"parameter '{name}' must be one of {list(spec.choices)}"
        if spec.column and ctx.working is not None and value not in ctx.working.columns:
            return f"parameter '{name}' names an unknown column: {value!r}"
        return None
    if spec.kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"parameter '{name}' must be an integer"
        if spec.minimum is not None and value < spec.minimum:
            return f"parameter '{name}' is below its minimum"
        if spec.maximum is not None and value > spec.maximum:
            return f"parameter '{name}' is above its maximum"
        return None
    if spec.kind == "list[str]":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return f"parameter '{name}' must be a list of strings"
        if len(value) > MAX_STATS_COLUMNS:
            return f"parameter '{name}' exceeds the column limit"
        if spec.choices and any(item not in spec.choices for item in value):
            return f"parameter '{name}' must contain only {list(spec.choices)}"
        if spec.column and ctx.working is not None:
            for item in value:
                if item not in ctx.working.columns:
                    return f"parameter '{name}' names an unknown column: {item!r}"
        return None
    return f"parameter '{name}' has an unsupported type specification"


def validate_tool_call(name: str, params: dict, ctx: ToolContext) -> tuple[bool, dict, str | None]:
    """Return (accepted, normalized_params, reason). Never raises on bad input."""
    if not isinstance(name, str) or name not in TOOL_REGISTRY:
        return False, {}, f"unknown tool: {name!r}"
    spec = TOOL_REGISTRY[name]
    if not isinstance(params, dict):
        return False, {}, "params must be an object"
    unknown = set(params) - set(spec.params)
    if unknown:
        return False, {}, f"unexpected parameter(s): {sorted(unknown)}"
    normalized: dict = {}
    for key, pspec in spec.params.items():
        if key not in params:
            if pspec.required:
                return False, {}, f"missing required parameter: {key}"
            normalized[key] = None
            continue
        problem = _validate_scalar(key, params[key], pspec, ctx)
        if problem:
            return False, {}, problem
        normalized[key] = params[key]
    if spec.side_effect == "destructive" and not ctx.user_confirmed:
        return False, {}, "destructive tool requires explicit user confirmation"
    return True, normalized, None


# ---------------------------------------------------------------------------
# Deterministic tool implementations
# ---------------------------------------------------------------------------

def _inspect_dataset(ctx: ToolContext, params: dict) -> dict:
    frame = ctx.frame
    if len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
        return {"error": f"dataset exceeds agent limits ({MAX_ROWS} rows / {MAX_COLUMNS} columns)"}
    ctx.profiles = infer_columns(frame)
    roles = suggest_roles(ctx.profiles)
    numbers = [p.name for p in ctx.profiles if p.is_numeric]
    x = roles.x or (numbers[0] if numbers else None)
    y = roles.y or next((c for c in numbers if c != x), None)
    if x is None or y is None or x == y:
        ctx.quality = {
            "rows": len(frame), "columns": list(map(str, frame.columns)),
            "numeric_columns": numbers, "n_valid_pairs": 0,
            "duplicate_headers": list(ctx.load_info.get("duplicate_headers") or []),
            "ambiguous_roles": True, "missing": 0, "invalid": 0, "nonfinite": 0,
            "invalid_ratio": {}, "suggested_x": x, "suggested_y": y,
            "warnings": ["Fewer than two usable numeric columns were found."],
        }
        return ctx.quality

    plan = build_plan(ctx.profiles, x=x, y=y, extra_numeric=tuple(numbers))
    cleaned = apply_cleaning(frame, plan)
    ctx.cleaning = cleaned
    ctx.working = cleaned.working
    xv, yv, _ = paired_values(cleaned, x, y)
    ctx.x_values, ctx.y_values = xv, yv
    ctx.pair_mask = cleaned.usable_pairs(x, y)
    unc = roles.uncertainty
    ctx.roles = {
        "x": x, "y": y, "group": roles.group, "time": roles.time,
        "uncertainty": unc, "numeric_columns": numbers,
    }

    invalid_ratio = {}
    total_missing = total_invalid = total_nonfinite = 0
    for p in ctx.profiles:
        if not p.is_numeric:
            continue
        invalid_ratio[p.name] = round(
            (p.n_invalid + p.n_nonfinite) / max(p.n_total, 1), 6
        )
        total_missing += p.n_missing
        total_invalid += p.n_invalid
        total_nonfinite += p.n_nonfinite
    duplicate_headers = list(ctx.load_info.get("duplicate_headers") or [])
    warnings = []
    if total_invalid or total_missing or total_nonfinite:
        warnings.append(
            "Invalid/missing/non-finite cells were detected. They are excluded from "
            "fitting by pairwise completeness but remain in the cleaned dataset; "
            "no values were imputed or coerced to zero."
        )
    if duplicate_headers:
        warnings.append("Duplicate header names require the user to select the intended columns.")
    if roles.ambiguous:
        warnings.append("Column roles are ambiguous; confirm X/Y before interpreting.")

    ctx.quality = {
        "rows": len(frame),
        "columns": list(map(str, frame.columns)),
        "numeric_columns": numbers,
        "n_valid_pairs": len(xv),
        "duplicate_headers": duplicate_headers,
        "ambiguous_roles": bool(roles.ambiguous),
        "missing": int(total_missing),
        "invalid": int(total_invalid),
        "nonfinite": int(total_nonfinite),
        "invalid_ratio": invalid_ratio,
        "suggested_x": x,
        "suggested_y": y,
        "suggested_uncertainty": unc,
        "warnings": warnings,
    }
    return ctx.quality


def _profile_columns(ctx: ToolContext, params: dict) -> dict:
    columns = params.get("columns") or [p.name for p in ctx.profiles]
    wanted = set(columns)
    return {"profiles": [
        {"name": p.name, "kind": p.kind, "n_total": p.n_total,
         "n_valid": p.n_valid, "n_missing": p.n_missing,
         "n_invalid": p.n_invalid, "n_nonfinite": p.n_nonfinite}
        for p in ctx.profiles if p.name in wanted
    ]}


def _describe_statistics(ctx: ToolContext, params: dict) -> dict:
    out = {}
    for name in params["columns"]:
        summary = describe_numeric(ctx.working[name])
        out[name] = {key: summary.get(key) for key in (
            "n_valid", "n_total", "mean", "median", "std_sample", "min", "max",
            "q1", "q3", "ci_mean_95", "constant",
        )}
    return {"statistics": out}


def _correlation_analysis(ctx: ToolContext, params: dict) -> dict:
    x, y, method = params["x"], params["y"], params["method"]
    xv = coerce_numeric(ctx.working[x]).values
    yv = coerce_numeric(ctx.working[y]).values
    corr = correlation(xv, yv, method=method)
    cov = covariance(xv, yv)
    return {"correlation": corr, "covariance": cov}


def _outlier_scan(ctx: ToolContext, params: dict) -> dict:
    values = coerce_numeric(ctx.working[params["column"]]).values
    result = outlier_diagnostics(values)
    return {"outliers": result, "note": "Flags only; no observation was removed."}


def _weights_for(ctx: ToolContext, column: str | None, mask: np.ndarray):
    if column is None:
        return None
    values = coerce_numeric(ctx.working[column]).values[mask]
    try:
        return inverse_variance_weights(values)
    except ValueError:
        return "invalid"


def _fit_curve(ctx: ToolContext, params: dict) -> dict:
    if ctx.working is None:
        return {"error": "inspect_dataset must run first"}
    x, y = params["x"], params["y"]
    xv = coerce_numeric(ctx.working[x]).values
    yv = coerce_numeric(ctx.working[y]).values
    mask = np.isfinite(xv) & np.isfinite(yv)
    weights = _weights_for(ctx, params.get("weights"), mask)
    if isinstance(weights, str) and weights == "invalid":
        return {"error": "selected uncertainty column contains invalid values or inverse-variance weights outside the numerical range"}
    fit = fit_model(
        params["model"], xv[mask], yv[mask], weights,
        degree=params.get("degree") or 2, x_label=x, y_label=y,
    )
    ctx.fit_counter += 1
    ref = f"fit_{ctx.fit_counter}"
    ctx.fits[ref] = fit
    return {
        "fit_ref": ref, "model": params["model"], "success": fit.success,
        "reason": fit.reason, "equation": fit.equation,
        "parameters": fit.parameters, "parameter_errors": fit.parameter_errors,
        "metrics": fit.metrics, "n_observations": fit.n_observations,
        "n_excluded": fit.n_excluded, "weighted": fit.weighted,
        "warnings": fit.warnings,
    }


def _diagnose_fit(ctx: ToolContext, params: dict) -> dict:
    from agent_diagnostics import diagnose_fit

    ref = params["fit_ref"]
    if ref not in ctx.fits:
        return {"error": f"unknown fit reference: {ref}"}
    fit = ctx.fits[ref]
    return {"diagnosis": diagnose_fit(fit, ctx.x_values, ctx.y_values), "fit_ref": ref}


def _render_plot(ctx: ToolContext, params: dict) -> dict:
    config = {
        "x": params["x"], "y": params["y"], "group": params.get("group"),
        "time": params.get("time"), "uncertainty": None, "secondary_y": [],
        "bins": 30, "fit_result": None,
        "numeric_columns": ctx.roles.get("numeric_columns", []),
    }
    spec = build_chart(params["plot_type"], ctx.working, config)
    return {"plot_type": params["plot_type"], "valid": spec.valid,
            "n_rows": spec.n_rows, "reason": spec.reason,
            "warnings": spec.warnings, "notes": spec.notes}


def _compare_models(ctx: ToolContext, params: dict) -> dict:
    """Fit a small, validated set of models and rank them by computed metrics."""
    if ctx.working is None:
        return {"error": "inspect_dataset must run first"}
    x, y = params["x"], params["y"]
    xv = coerce_numeric(ctx.working[x]).values
    yv = coerce_numeric(ctx.working[y]).values
    mask = np.isfinite(xv) & np.isfinite(yv)
    models = list(dict.fromkeys(params.get("models") or ["linear", "polynomial"]))[:3]
    fits = [
        fit_model(model, xv[mask], yv[mask], None,
                  degree=params.get("degree") or 2, x_label=x, y_label=y)
        for model in models
    ]
    return {
        "comparison": rank_models(fits),
        "n_observations": int(mask.sum()),
        "models_requested": models,
        "ranking": "AIC when available, otherwise adjusted R²; computed locally.",
        "note": "Model comparison is descriptive; it is not proof of a physical mechanism.",
    }


def _evidence_summary(ctx: ToolContext, params: dict) -> dict:
    """Summarise only fits actually computed during this run."""
    entries = []
    for ref, fit in ctx.fits.items():
        metrics = dict(getattr(fit, "metrics", {}) or {})
        entries.append({
            "result_id": f"fit.{ref}",
            "fit_ref": ref,
            "model": getattr(fit, "model", None),
            "success": bool(getattr(fit, "success", False)),
            "n_observations": getattr(fit, "n_observations", 0),
            "r2": metrics.get("r2"),
            "rmse": metrics.get("rmse"),
        })
    return {
        "evidence": entries,
        "n_fits": len(entries),
        "n_valid_pairs": len(ctx.x_values) if ctx.x_values is not None else 0,
        "note": "IDs reference executed fit events; no values were invented or imputed.",
    }


def _time_series_summary(ctx: ToolContext, params: dict) -> dict:
    """Descriptive lag summary for an ordered numeric series; no forecasting."""
    if ctx.working is None:
        return {"error": "inspect_dataset must run first"}
    time_values = coerce_numeric(ctx.working[params["time"]]).values
    values = coerce_numeric(ctx.working[params["value"]]).values
    mask = np.isfinite(values)
    time_finite = np.isfinite(time_values)
    if time_finite.all() and np.all(np.diff(time_values) > 0):
        order = np.argsort(time_values)
        ordering = "strictly increasing numeric time column"
    else:
        order = np.arange(len(values))
        ordering = "original row order (time column is not strictly increasing numeric)"
        mask &= time_finite
    series = values[order][mask[order]]
    if series.size < 3:
        return {"error": "at least three finite ordered values are required"}
    steps = np.diff(series)
    lags = {}
    for lag in range(1, min(int(params.get("max_lag") or 1), series.size - 2) + 1):
        lags[str(lag)] = correlation(series[:-lag], series[lag:], method="pearson")
    return {
        "n_points": int(series.size), "ordering": ordering,
        "mean_step": float(np.mean(steps)),
        "std_step": float(np.std(steps, ddof=1)) if steps.size > 1 else None,
        "lag_correlations": lags,
        "note": "Descriptive lag associations only; no forecasting, seasonality claim or causal inference.",
    }


def _request_confirmation(ctx: ToolContext, params: dict) -> dict:
    return {"confirmed": True, "action": params["action"],
            "note": "User confirmation was supplied; no destructive operation is performed by this tool."}


def _declare_insufficient(ctx: ToolContext, params: dict) -> dict:
    return {"state": "INSUFFICIENT_EVIDENCE", "reason": params["reason"]}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "inspect_dataset": ToolSpec("inspect_dataset", _inspect_dataset, {},
                                description="Structured data-quality summary and role inference."),
    "profile_columns": ToolSpec("profile_columns", _profile_columns,
                                {"columns": ParamSpec("list[str]", required=False, column=True)},
                                description="Per-column type and validity counts."),
    "describe_statistics": ToolSpec("describe_statistics", _describe_statistics,
                                    {"columns": ParamSpec("list[str]", column=True)},
                                    description="Descriptive statistics for named columns."),
    "correlation_analysis": ToolSpec("correlation_analysis", _correlation_analysis, {
        "x": ParamSpec("str", column=True), "y": ParamSpec("str", column=True),
        "method": ParamSpec("str", choices=("pearson", "spearman")),
    }, description="Pearson or Spearman correlation on pairwise-complete values."),
    "outlier_scan": ToolSpec("outlier_scan", _outlier_scan,
                             {"column": ParamSpec("str", column=True)},
                             description="IQR outlier flags (never removal)."),
    "fit_curve": ToolSpec("fit_curve", _fit_curve, {
        "x": ParamSpec("str", column=True), "y": ParamSpec("str", column=True),
        "model": ParamSpec("str", choices=tuple(MODEL_SPECS)),
        "degree": ParamSpec("int", required=False, minimum=1, maximum=MAX_DEGREE),
        "weights": ParamSpec("optional_str", required=False, column=True),
    }, description="Fit one allowlisted model; returns parameters and metrics."),
    "diagnose_fit": ToolSpec("diagnose_fit", _diagnose_fit,
                             {"fit_ref": ParamSpec("str")},
                             description="Deterministic fit-quality classification."),
    "compare_models": ToolSpec("compare_models", _compare_models, {
        "x": ParamSpec("str", column=True), "y": ParamSpec("str", column=True),
        "models": ParamSpec("list[str]", required=False,
                            choices=tuple(MODEL_SPECS)),
        "degree": ParamSpec("int", required=False, minimum=1, maximum=MAX_DEGREE),
    }, description="Fit up to three allowlisted models and rank them by computed AIC/adjusted R²."),
    "evidence_summary": ToolSpec("evidence_summary", _evidence_summary, {},
                                 description="List computed fit result IDs and metrics from this run."),
    "time_series_summary": ToolSpec("time_series_summary", _time_series_summary, {
        "time": ParamSpec("str", column=True), "value": ParamSpec("str", column=True),
        "max_lag": ParamSpec("int", required=False, minimum=1, maximum=5),
    }, description="Descriptive step statistics and lag correlations for an ordered numeric series."),
    "render_plot": ToolSpec("render_plot", _render_plot, {
        "plot_type": ParamSpec("str", choices=tuple(PLOT_TYPES)),
        "x": ParamSpec("str", column=True), "y": ParamSpec("str", column=True),
        "group": ParamSpec("optional_str", required=False, column=True),
        "time": ParamSpec("optional_str", required=False, column=True),
    }, description="Build an allowlisted chart and report its warnings."),
    "request_confirmation": ToolSpec("request_confirmation", _request_confirmation,
                                     {"action": ParamSpec("str", choices=("remove_duplicate_rows", "write_export_files"))},
                                     side_effect="destructive",
                                     description="Requires explicit user confirmation."),
    "declare_insufficient": ToolSpec("declare_insufficient", _declare_insufficient,
                                     {"reason": ParamSpec("str")},
                                     side_effect="terminal",
                                     description="Halts with an explicit evidence gap."),
}


def registry_manifest() -> list[dict]:
    """Compact, safe description of the allowlist sent to the planner."""
    return [
        {
            "tool": spec.name,
            "params": {
                name: {"type": p.kind, "required": p.required,
                       **({"choices": list(p.choices)} if p.choices else {}),
                       **({"min": p.minimum, "max": p.maximum} if p.maximum is not None else {})}
                for name, p in spec.params.items()
            },
            "description": spec.description,
        }
        for spec in TOOL_REGISTRY.values()
    ]


def execute_tool(name: str, params: dict, ctx: ToolContext) -> ToolResult:
    """Validate, bound, and dispatch one tool call. Never raises."""
    started = time.monotonic()
    accepted, normalized, reason = validate_tool_call(name, params, ctx)
    if not accepted:
        return ToolResult(False, str(name), params if isinstance(params, dict) else {},
                          0.0, error=f"validation rejected: {reason}")
    if time.monotonic() > ctx.deadline:
        return ToolResult(False, name, normalized, 0.0, error="global deadline exceeded")
    spec = TOOL_REGISTRY[name]
    remaining = max(ctx.deadline - time.monotonic(), 0.1)
    timeout = min(MAX_TOOL_S, remaining)
    try:
        # A Python thread cannot be forcibly stopped on timeout. Isolate its
        # mutable state so late completion cannot alter a later audited result.
        def run_isolated():
            worker_ctx = copy.deepcopy(ctx)
            return spec.fn(worker_ctx, normalized), worker_ctx

        future = _EXECUTOR.submit(run_isolated)
        payload, worker_ctx = future.result(timeout=timeout)
    except FutureTimeout:
        future.cancel()  # A running thread may still finish on its isolated copy.
        ctx.deadline = min(ctx.deadline, time.monotonic())
        return ToolResult(False, name, normalized,
                          (time.monotonic() - started) * 1000,
                          error=f"tool exceeded its {timeout:.1f}s budget; further tools stopped")
    except Exception as exc:
        return ToolResult(False, name, normalized,
                          (time.monotonic() - started) * 1000,
                          error=provider_config.redact(f"{type(exc).__name__}: {exc}"))
    duration = (time.monotonic() - started) * 1000
    if not isinstance(payload, dict):
        return ToolResult(False, name, normalized, duration, error="tool returned a non-object result")
    if payload.get("error"):
        return ToolResult(False, name, normalized, duration,
                          result={"error": payload["error"]}, error=payload["error"])
    # Commit tool state only for a completed, successful call.
    ctx.__dict__.update(worker_ctx.__dict__)
    # Keep the audit log small and JSON-safe.
    try:
        encoded = json.dumps(payload, allow_nan=False, default=str)
        payload = json.loads(encoded)
    except (TypeError, ValueError):
        payload = {"summary": "result omitted (not JSON serializable)"}
    return ToolResult(True, name, normalized, duration, result=payload)
