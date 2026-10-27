# Agent tool registry

The registry is the **only** execution path available to the analysis agent.
It is defined in `agent_tools.TOOL_REGISTRY` and described to the planner by
`agent_tools.registry_manifest()`.

## Dispatch contract

```python
accepted, normalized_params, reason = validate_tool_call(name, params, ctx)
result: ToolResult = execute_tool(name, params, ctx)
```

- `name` must be an exact key of `TOOL_REGISTRY` (no aliases, dotted paths or
  private names).
- `params` must be a JSON object whose keys are exactly the declared
  parameters. Unknown or missing required keys are rejected.
- Values are checked by type (`str`, `int`, `list[str]`, `optional_str`),
  choices, numeric bounds, and column existence in the cleaned working frame.
  `bool` is rejected where an `int` is required.
- `side_effect="destructive"` tools require `ctx.user_confirmed is True`.
- Each call runs under a 5 s per-tool budget and a 30 s global deadline, and
  returns a `ToolResult` carrying a compact, JSON-safe `result_digest`.

## Tools

There are **13** registered tools (the original ten plus three added in the
master-prompt phase). `tests/test_agent_tools.py` asserts the manifest size and
that the manifest is exactly the registry.

| Tool | Parameters | Deterministic source | Side effect | Purpose |
| --- | --- | --- | --- | --- |
| `inspect_dataset` | none | `infer_columns`, `suggest_roles`, `build_plan`, `apply_cleaning`, `paired_values` | read-only | Structured data-quality summary: rows, numeric columns, missing/invalid/non-finite counts, duplicate headers, ambiguous roles, complete X/Y pairs, warnings. |
| `profile_columns` | `columns?: list[str]` | `infer_columns` | read-only | Per-column kind and validity counts. |
| `describe_statistics` | `columns: list[str]` (<=10) | `statistics_core.describe_numeric` | read-only | Mean, median, SD, quartiles, Student-t CI. |
| `correlation_analysis` | `x`, `y`, `method: pearson\|spearman` | `statistics_core.correlation`, `covariance` | read-only | Association on pairwise-complete finite values. |
| `outlier_scan` | `column` | `statistics_core.outlier_diagnostics` | read-only | IQR flags only; never removes observations. |
| `fit_curve` | `x`, `y`, `model`, `degree?: 1..4`, `weights?: column` | `fitting_core.fit_model` | read-only | Fits one of `linear`, `polynomial`, `exponential`, `logarithmic`, `power`; returns parameters, errors, metrics, `fit_ref`. |
| `diagnose_fit` | `fit_ref` | `agent_diagnostics.diagnose_fit` | read-only | `PASS` / `POOR_FIT` / `FAILED` / `INSUFFICIENT` with reasons. |
| `compare_models` | `x`, `y`, `models?: list[str]` (<=3, allowlisted), `degree?: 1..4` | `fitting_core.fit_model`, `compare_models` | read-only | Fits up to three models on the same pairs and ranks them by computed AIC / adjusted R². |
| `evidence_summary` | none | `ToolContext.fits` | read-only | Lists computed fit result IDs, models, R², RMSE and observation counts from this run. |
| `time_series_summary` | `time`, `value`, `max_lag?: 1..5` | `statistics_core.correlation`, NumPy | read-only | Descriptive step statistics and lag correlations; explicitly no forecasting or causal claim. |
| `render_plot` | `plot_type`, `x`, `y`, `group?`, `time?` | `visualization_core.build_chart` | read-only | Builds one of 10 allowlisted charts; reports validity, row count, warnings and notes. |
| `request_confirmation` | `action: remove_duplicate_rows\|write_export_files` | none | **destructive - gated** | Records explicit user confirmation; never performs the action itself. |
| `declare_insufficient` | `reason` | none | terminal | Stops the run with a stated evidence gap. |

## Parameter types

```python
@dataclass(frozen=True)
class ParamSpec:
    kind: str          # "str" | "int" | "list[str]" | "optional_str"
    required: bool
    choices: tuple
    minimum: float | None
    maximum: float | None
    column: bool       # value must exist in ctx.working.columns
```

## Explicitly excluded

The registry contains no tool for running Python, evaluating expressions,
reading arbitrary paths, writing arbitrary files, issuing shell commands,
making network requests, or removing rows. The only network access in the
whole system is `ask_muse.py`, used for plan proposals and optional report
sections, and it is gated by `BASETEN_API_KEY` plus explicit user consent.

## Bounds

| Limit | Value |
| --- | --- |
| Plan steps | 8 |
| Retries | 2 |
| Fit attempts | 3 |
| Per-tool time | 5 s |
| Whole-run time | 30 s |
| Rows / columns | 50,000 / 20 |
| Polynomial degree | 4 |
| Statistics columns per call | 10 |
| Fallback models | 3 |

A static test (`tests/test_agent_tools.py::test_source_contains_no_dynamic_code_execution_primitives`)
reads `agent_tools.py` and asserts `eval(`, `exec(`, `compile(`, `subprocess`,
`os.system`, `pickle.loads` and `__import__` are absent. Plan strings containing
`import `, `eval(`, `exec(`, `open(`, `lambda `, `__` or code fences are
rejected by `agent_planner.validate_plan` before execution.
