"""One result schema used by the UI, the CLI and every export.

All numeric values in this schema come from the deterministic engines in
``statistics_core`` / ``fitting_core``. AI prose, when present, is stored
separately under ``ai`` and is always labelled as model-generated.
"""

from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

SCHEMA_VERSION = "2.0"


def json_safe(value):
    """Recursively convert to JSON-safe values; non-finite numbers become null."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "as_dict"):
        return json_safe(value.as_dict())
    return str(value)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    """UTF-8 CSV with formula-injection-safe leading characters."""
    buffer = io.StringIO(newline="")
    safe = frame.copy()
    for column in safe.columns:
        if safe[column].dtype == object or str(safe[column].dtype).startswith("str"):
            safe[column] = safe[column].map(
                lambda value: ("'" + str(value)) if isinstance(value, str)
                and value[:1] in ("=", "+", "-", "@") else value
            )
    safe.to_csv(buffer, index=False, quoting=csv.QUOTE_MINIMAL)
    return buffer.getvalue().encode("utf-8-sig")


def build_result(
    *,
    source: dict,
    roles: dict,
    cleaning: dict,
    statistics: dict,
    correlation: dict,
    outliers: dict,
    fit,
    model_comparison: list[dict],
    model_suggestions: list[dict],
    domain: dict,
    chart_summaries: list[dict],
    notes: list[str] | None = None,
    ai: dict | None = None,
) -> dict:
    """Assemble the single result object consumed by all exporters."""
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": json_safe(source),
        "roles": json_safe(roles),
        "cleaning": json_safe(cleaning),
        "statistics": json_safe(statistics),
        "correlation": json_safe(correlation),
        "outliers": json_safe(outliers),
        "fit": json_safe(fit.as_dict() if hasattr(fit, "as_dict") else fit) if fit else None,
        "model_comparison": json_safe(model_comparison),
        "model_suggestions": json_safe(model_suggestions),
        "domain": json_safe(domain),
        "visualizations": json_safe(chart_summaries),
        "notes": json_safe(notes or []),
        "ai": json_safe(ai),
    }
    warnings: list[str] = []
    for key in ("source", "cleaning", "domain"):
        block = result.get(key) or {}
        warnings.extend(block.get("warnings", []) if isinstance(block, dict) else [])
    if isinstance(result["fit"], dict):
        warnings.extend(result["fit"].get("warnings", []))
    result["warnings"] = json_safe([item for item in dict.fromkeys(warnings) if item])
    return result


def results_json(result: dict) -> bytes:
    return json.dumps(json_safe(result), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def ai_context(result: dict, *, max_chars: int = 28_000) -> dict:
    """Compact, deterministic-only context for the AI provider.

    Deliberately excludes any prior AI text, raw data rows and free-form user
    notes, so the model can only cite values computed by this application.
    Large blocks are progressively trimmed until the JSON fits ``max_chars``.
    """
    stats = {}
    for name, summary in (result.get("statistics") or {}).items():
        if not isinstance(summary, dict):
            continue
        stats[name] = {key: summary.get(key) for key in (
            "n_valid", "n_total", "n_missing_or_invalid", "n_infinite", "mean",
            "median", "std_sample", "min", "q1", "q3", "max", "ci_mean_95",
            "ci_mean_method", "constant",
        )}
    context = {
        "schema_version": result.get("schema_version"),
        "note": "All values below were computed locally. Do not invent any other numbers.",
        "source": {key: (result.get("source") or {}).get(key) for key in (
            "name", "rows", "columns", "delimiter", "encoding", "warnings"
        )},
        "roles": result.get("roles"),
        "cleaning": result.get("cleaning"),
        "statistics": stats,
        "correlation": result.get("correlation"),
        "outliers": result.get("outliers"),
        "fit": result.get("fit"),
        "model_comparison": result.get("model_comparison"),
        "model_suggestions": result.get("model_suggestions"),
        "domain": result.get("domain"),
        "warnings": result.get("warnings"),
    }
    def size() -> int:
        return len(json.dumps(json_safe(context), ensure_ascii=False, allow_nan=False))

    if size() > max_chars:
        # Keep the most decision-relevant blocks; drop the most verbose first.
        for key in ("model_suggestions", "model_comparison", "cleaning", "outliers"):
            context[key] = {"note": "Omitted from AI context to stay within the size limit."}
            if size() <= max_chars:
                return json_safe(context)
    if size() > max_chars:
        # With hundreds of numeric columns, truncate statistics rather than
        # exceed the provider's context budget.
        kept = {}
        for name, summary in (context.get("statistics") or {}).items():
            kept[name] = summary
            context["statistics"] = kept
            if size() > max_chars:
                del kept[name]
                break
        context["statistics"] = kept or {"note": "Statistics omitted (too many columns)."}
    if size() > max_chars:
        source = context.get("source") or {}
        if isinstance(source, dict) and source.get("columns"):
            source["columns"] = list(source["columns"])[:50]
    if size() > max_chars:
        context = {
            "note": "Context truncated to fit the AI size limit; use the exported results.json for full detail.",
            "roles": context.get("roles"),
            "fit": context.get("fit"),
            "correlation": context.get("correlation"),
            "warnings": context.get("warnings"),
        }
    return json_safe(context)


def _fmt(value) -> str:
    if value is None:
        return "not available"
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(item) for item in value)
    if isinstance(value, float):
        return f"{value:.6g}" if math.isfinite(value) else "not finite"
    return str(value)


def markdown_report(result: dict) -> str:
    """Deterministic report. AI sections, if any, are clearly attributed."""
    source = result.get("source") or {}
    roles = result.get("roles") or {}
    cleaning = result.get("cleaning") or {}
    fit = result.get("fit") or {}
    domain = result.get("domain") or {}
    stats = result.get("statistics") or {}
    corr = result.get("correlation") or {}
    outliers = result.get("outliers") or {}

    lines = [
        "# LabLens AI analysis report",
        "",
        f"- Generated (UTC): {result.get('generated_at_utc', 'unknown')}",
        f"- Schema version: {result.get('schema_version', 'unknown')}",
        f"- Source: {_fmt(source.get('name'))} ({_fmt(source.get('rows'))} rows, "
        f"{_fmt(len(source.get('columns') or []))} columns)",
        f"- Encoding / delimiter: {_fmt(source.get('encoding'))} / {_fmt(source.get('delimiter'))!r}",
        f"- SHA-256: `{_fmt(source.get('sha256'))}`",
        "",
        "## 1. Configuration",
        "",
        f"- X: {_fmt(roles.get('x'))}; Y: {_fmt(roles.get('y'))}",
        f"- Group: {_fmt(roles.get('group'))}; Time: {_fmt(roles.get('time'))}",
        f"- Uncertainty: {_fmt(roles.get('uncertainty'))}; "
        f"Secondary Y: {_fmt(roles.get('secondary_y'))}",
        f"- Model: {_fmt(fit.get('label') or fit.get('model'))}; "
        f"weighted: {_fmt(fit.get('weighted'))}",
        "",
        "## 2. Cleaning decisions",
        "",
        f"- Rows in: {_fmt(cleaning.get('rows_in'))}; rows out: {_fmt(cleaning.get('rows_out'))}",
        f"- Duplicate rows removed: {_fmt(cleaning.get('duplicates_removed'))}",
        f"- Rows excluded from fitting (invalid/incomplete pairs): "
        f"{_fmt(cleaning.get('invalid_pair_rows_excluded'))}",
        "- Invalid, missing and non-finite values were *not* converted to zero; they remain in the cleaned CSV.",
        "",
    ]
    for column in cleaning.get("columns", []) or []:
        lines.append(
            f"- `{column.get('name')}`: missing={_fmt(column.get('missing'))}, "
            f"invalid={_fmt(column.get('invalid'))}, nonfinite={_fmt(column.get('nonfinite'))}, "
            f"coerced={_fmt(column.get('coerced'))}, valid={_fmt(column.get('valid'))}"
        )
    lines += ["", "## 3. Descriptive statistics", ""]
    for column, summary in stats.items():
        if not isinstance(summary, dict):
            continue
        lines += [
            f"### {column}",
            "",
            f"- n valid / total: {_fmt(summary.get('n_valid'))} / {_fmt(summary.get('n_total'))}",
            f"- Mean: {_fmt(summary.get('mean'))}; median: {_fmt(summary.get('median'))}",
            f"- Sample SD (ddof={_fmt(summary.get('ddof'))}): {_fmt(summary.get('std_sample'))}",
            f"- Min / Q1 / Q3 / max: {_fmt(summary.get('min'))} / {_fmt(summary.get('q1'))} / "
            f"{_fmt(summary.get('q3'))} / {_fmt(summary.get('max'))}",
            f"- 95% t CI for the mean: {_fmt(summary.get('ci_mean_95'))} "
            f"({_fmt(summary.get('ci_mean_method'))})",
            "",
        ]
    lines += [
        "## 4. Association and diagnostics",
        "",
        f"- Correlation method: {_fmt(corr.get('method'))}",
        f"- Coefficient: {_fmt(corr.get('coefficient'))}; p-value: {_fmt(corr.get('p_value'))}",
        f"- Complete pairs: {_fmt(corr.get('n_valid'))}; excluded: {_fmt(corr.get('n_excluded'))}",
        f"- {_fmt(corr.get('caveat') or corr.get('reason'))}",
        f"- IQR outlier flags: {_fmt(outliers.get('n_low'))} low, {_fmt(outliers.get('n_high'))} high "
        f"(flagged only, never removed). {_fmt(outliers.get('caveat') or outliers.get('reason'))}",
        "",
        "## 5. Fit",
        "",
    ]
    if not fit.get("success"):
        lines += [f"Fit was not successful: {_fmt(fit.get('reason'))}", ""]
    else:
        lines += [
            f"- Equation: `{_fmt(fit.get('equation'))}`",
            f"- Observations used: {_fmt(fit.get('n_observations'))}; excluded: {_fmt(fit.get('n_excluded'))}",
            f"- Assumptions: {_fmt(fit.get('assumptions'))}",
            "",
            "| Parameter | Value | Std. error |",
            "| --- | ---: | ---: |",
        ]
        errors = fit.get("parameter_errors") or {}
        for name, value in (fit.get("parameters") or {}).items():
            lines.append(f"| {name} | {_fmt(value)} | {_fmt(errors.get(name))} |")
        metrics = fit.get("metrics") or {}
        lines += [
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
        for name in ("r2", "adjusted_r2", "rmse", "mae", "reduced_chi2", "aic",
                     "n_observations", "n_parameters", "degrees_of_freedom"):
            lines.append(f"| {name} | {_fmt(metrics.get(name))} |")
        if fit.get("x_range"):
            lines.append(f"\nFitted X range: {_fmt(fit['x_range'])}. Predictions outside it are extrapolations.")
    lines += ["", "## 6. Model comparison", "", "| Model | OK | n | Params | R² | Adj. R² | AIC | RMSE |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in result.get("model_comparison") or []:
        lines.append(
            f"| {_fmt(row.get('label') or row.get('model'))} | {_fmt(row.get('success'))} | "
            f"{_fmt(row.get('n_observations'))} | {_fmt(row.get('n_parameters'))} | "
            f"{_fmt(row.get('r2'))} | {_fmt(row.get('adjusted_r2'))} | {_fmt(row.get('aic'))} | "
            f"{_fmt(row.get('rmse'))} |"
        )
    lines += ["", "AIC comparisons are meaningful only for fits on the same observations and "
              "the same weighting.", "", "## 7. Domain interpretation", "",
              f"- Module: {_fmt(domain.get('label'))}",
              f"- Description: {_fmt(domain.get('description'))}"]
    for assumption in domain.get("assumptions") or []:
        lines.append(f"- Assumption: {assumption}")
    for item in domain.get("derived") or []:
        lines.append(f"- Computed: {_fmt(item.get('name'))} = {_fmt(item.get('value'))} "
                     f"{_fmt(item.get('unit') or '')} ({_fmt(item.get('source'))})")
    for hypothesis in domain.get("hypotheses") or []:
        lines.append(f"- {hypothesis}")
    for warning in domain.get("warnings") or []:
        lines.append(f"- Limitation: {warning}")

    lines += ["", "## 8. Figures", ""]
    for chart in result.get("visualizations") or []:
        lines.append(f"- {_fmt(chart.get('label'))}: {_fmt(chart.get('n_rows'))} rows plotted "
                     f"({_fmt(chart.get('file'))})")
        for warning in chart.get("warnings") or []:
            lines.append(f"  - Caution: {warning}")

    lines += ["", "## 9. Limitations and provenance", "",
              "- All numbers above were computed locally from the uploaded CSV; none were generated by an AI model.",
              "- Statistical confidence intervals describe sampling variability under stated assumptions, "
              "not instrument accuracy.",
              "- No measurement uncertainties are invented; error bars appear only when an uncertainty column is supplied.",
              "- Correlation and fitted coefficients do not establish causation.",
              "- Results outside the fitted X range are extrapolations."]
    for note in result.get("notes") or []:
        lines.append(f"- {note}")
    for warning in result.get("warnings") or []:
        lines.append(f"- {warning}")

    ai = result.get("ai")
    if ai:
        structured = ai.get("structured") or {}
        lines += ["", "## 10. AI-generated interpretation (unverified hypotheses)", "",
                  f"Provider model: {_fmt(ai.get('model'))}. The following text was generated by an AI "
                  "model from the computed context above. It is not experimental evidence and may be wrong.",
                  ""]
        for section in structured.get("sections") or []:
            lines += [f"### {section.get('title')}", "", str(section.get("content", "")), ""]
        for i, claim in enumerate(structured.get("claims") or [], start=1):
            lines += [f"**Claim {i}** ({_fmt(claim.get('evidence_type'))}): {claim.get('claim')}",
                      f"- Evidence: {claim.get('evidence')}",
                      f"- Confidence/uncertainty: {claim.get('confidence_or_uncertainty')}",
                      f"- Limitation: {claim.get('limitation')}",
                      f"- Proposed verification: {claim.get('proposed_verification')}", ""]
    else:
        lines += ["", "## 10. AI-generated interpretation", "",
                  "Not requested, or the provider was unavailable. All deterministic results above "
                  "are complete without AI."]
    return "\n".join(lines) + "\n"


def export_bundle(
    result: dict,
    *,
    cleaned_frame: pd.DataFrame | None = None,
    descriptive_table: pd.DataFrame | None = None,
    charts: dict[str, bytes] | None = None,
) -> dict[str, bytes]:
    """Return ``{filename: bytes}`` for every configured export artifact."""
    files: dict[str, bytes] = {"results.json": results_json(result)}
    if cleaned_frame is not None:
        files["cleaned_data.csv"] = _csv_bytes(cleaned_frame)
    if descriptive_table is not None:
        files["statistics.csv"] = _csv_bytes(descriptive_table)
    fit = result.get("fit") or {}
    if fit.get("success"):
        errors = fit.get("parameter_errors") or {}
        params = pd.DataFrame([
            {"parameter": name, "value": value, "std_error": errors.get(name)}
            for name, value in (fit.get("parameters") or {}).items()
        ])
        files["fit_parameters.csv"] = _csv_bytes(params)
        metrics = fit.get("metrics") or {}
        files["fit_metrics.csv"] = _csv_bytes(pd.DataFrame(
            [{"metric": key, "value": value} for key, value in metrics.items()]
        ))
    else:
        files["fit_parameters.csv"] = _csv_bytes(pd.DataFrame(
            [{"parameter": "not fitted", "value": fit.get("reason") or "No successful fit"}]
        ))
        files["fit_metrics.csv"] = _csv_bytes(pd.DataFrame(
            [{"metric": "status", "value": fit.get("reason") or "No successful fit"}]
        ))
    files["report.md"] = markdown_report(result).encode("utf-8")
    for name, payload in (charts or {}).items():
        files[name] = payload
    return files
