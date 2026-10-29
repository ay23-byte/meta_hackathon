"""One result schema used by the UI, the CLI and every export.

All numeric values in this schema come from the deterministic engines in
``statistics_core`` / ``fitting_core``. AI prose, when present, is stored
separately under ``ai`` and is always labelled as model-generated.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import platform
import re
from datetime import datetime, timezone
from importlib import metadata

import numpy as np
import pandas as pd

from evidence_trace import build_evidence_ledger
from insight_engine import discover_insights
from uncertainty_engine import linear_parameter_intervals

SCHEMA_VERSION = "2.0"


def safe_archive_name(name: str) -> str:
    """Validate one relative archive/output file name.

    Rejects absolute paths, Windows drive letters, parent traversal, empty
    path components, backslashes and control characters. Used by both the ZIP
    writer and the CLI file writer so an export name can never escape its
    destination directory.
    """
    if not isinstance(name, str) or not name or name != name.strip():
        raise ValueError("Export file name must be a non-empty, clean string.")
    if any(ord(char) < 32 for char in name) or "\\" in name:
        raise ValueError("Export file name contains unsafe characters.")
    if name.startswith(("/", "~")):
        raise ValueError("Export file name must be relative.")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts) or ":" in parts[0]:
        raise ValueError("Export file name contains an unsafe path component.")
    return name


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
    """UTF-8 CSV with spreadsheet formula injection mitigated in cells and headers."""
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@"):
            return "'" + value
        if isinstance(value, str) and value[:1] in ("\t", "\r", "\n"):
            return "'" + value
        return value

    buffer = io.StringIO(newline="")
    safe = frame.map(safe_cell)
    safe.columns = [safe_cell(column) for column in frame.columns]
    safe.to_csv(buffer, index=False, quoting=csv.QUOTE_MINIMAL)
    return buffer.getvalue().encode("utf-8-sig")


def software_versions() -> dict:
    """Record a small allowlist of runtime versions, never environment values or paths."""
    packages = {}
    for name in ("numpy", "pandas", "scipy", "streamlit", "altair", "matplotlib", "openai"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "packages": packages}


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
        "software": software_versions(),
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
    result["insights"] = discover_insights(result)
    result["uncertainty"] = linear_parameter_intervals(result["fit"], result["roles"])
    result["evidence_ledger"] = build_evidence_ledger(result)
    return result


def results_json(result: dict) -> bytes:
    # ASCII JSON remains valid UTF-8 and also survives legacy Windows text
    # readers using a non-UTF-8 default encoding; JSON decoding restores Unicode.
    return json.dumps(json_safe(result), ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8")


def _evidence_slug(value, limit: int = 24) -> str:
    """Short, safe ASCII fragment for a computed result ID."""
    text = "".join(ch if (ch.isascii() and (ch.isalnum() or ch in "_-.")) else "_"
                   for ch in str(value))
    return (text.strip("_.")[:limit] or "x")


def evidence_index(result: dict, *, limit: int = 12) -> dict:
    """Compact ID -> computed-values map for evidence-linked AI claims.

    IDs are stable enough for a reproducible audit trail and contain only
    characters allowed by ``ask_muse``. Every value is copied from the local
    deterministic result; no raw rows or AI prose are included.
    """
    index: dict[str, dict] = {}

    def add(base: str, label: str, values: dict):
        key = _evidence_slug(base, 40)
        candidate, suffix = key, 2
        while candidate in index:
            candidate = f"{key}_{suffix}"
            suffix += 1
        if len(candidate) > 48:
            candidate = candidate[:48]
        index[candidate] = {"label": label, **json_safe(values)}

    source = result.get("source") or {}
    add("dataset.source", "Dataset provenance", {
        "rows": source.get("rows"), "n_columns": len(source.get("columns") or []),
        "sha256": source.get("sha256"), "encoding": source.get("encoding"),
    })
    cleaning = result.get("cleaning") or {}
    add("cleaning.summary", "Cleaning summary", {
        "rows_in": cleaning.get("rows_in"), "rows_out": cleaning.get("rows_out"),
        "duplicates_removed": cleaning.get("duplicates_removed"),
        "invalid_pair_rows_excluded": cleaning.get("invalid_pair_rows_excluded"),
    })
    corr = result.get("correlation") or {}
    if isinstance(corr, dict):
        add(f"corr.{corr.get('method') or 'association'}", "Association", {
            key: corr.get(key) for key in ("method", "coefficient", "p_value", "n_valid")
        })
    fit = result.get("fit") or {}
    if isinstance(fit, dict) and fit:
        add(f"fit.{fit.get('model') or 'model'}", "Selected fit", {
            "success": fit.get("success"), "model": fit.get("model"),
            "label": fit.get("label"), "n_observations": fit.get("n_observations"),
            "parameters": fit.get("parameters"),
            "r2": (fit.get("metrics") or {}).get("r2"),
            "adjusted_r2": (fit.get("metrics") or {}).get("adjusted_r2"),
            "rmse": (fit.get("metrics") or {}).get("rmse"),
        })
    for row in (result.get("model_comparison") or [])[:3]:
        if isinstance(row, dict):
            add(f"compare.{row.get('model') or 'model'}", "Model comparison", {
                key: row.get(key) for key in
                ("model", "success", "n_observations", "r2", "adjusted_r2", "aic", "rmse")
            })
    for name, summary in (result.get("statistics") or {}).items():
        if not isinstance(summary, dict):
            continue
        add(f"stat.{name}", "Descriptive statistics", {
            "column": name,
            **{key: summary.get(key) for key in
               ("n_valid", "mean", "median", "std_sample", "min", "max", "ci_mean_95")},
        })
    outliers = result.get("outliers") or {}
    if isinstance(outliers, dict) and outliers:
        add("outliers.summary", "Outlier diagnostics", {
            key: outliers.get(key) for key in ("n_valid", "n_low", "n_high", "method")
        })
    return dict(list(index.items())[:max(1, limit)])


def ai_context(result: dict, *, max_chars: int = 28_000,
               research_question: str | None = None) -> dict:
    """Compact, deterministic-only context for the AI provider.

    Deliberately excludes any prior AI text, raw data rows and free-form user
    notes, so the model can only cite values computed by this application.
    Includes bounded ``result_ids`` / ``evidence_index`` entries so claims can
    be linked to computed values. Large blocks are progressively trimmed until
    the JSON fits ``max_chars``.
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
    evidence = evidence_index(result)
    context = {
        "schema_version": result.get("schema_version"),
        "note": "All values below were computed locally. Do not invent any other numbers.",
        "research_question": (str(research_question).strip()[:500]
                              if research_question else None),
        "result_ids": list(evidence),
        "evidence_index": evidence,
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

    def shrink_evidence(keep: int):
        """Keep IDs and their evidence values consistent while trimming."""
        trimmed = dict(list(evidence.items())[:keep])
        context["evidence_index"] = trimmed
        context["result_ids"] = list(trimmed)
        return trimmed

    if size() > max_chars:
        for keep in (6, 3, 1):
            shrink_evidence(keep)
            if size() <= max_chars:
                return json_safe(context)
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
        minimal_evidence = shrink_evidence(1)
        context = {
            "note": "Context truncated to fit the AI size limit; use the exported results.json for full detail.",
            "research_question": context.get("research_question"),
            "roles": context.get("roles"),
            "fit": context.get("fit"),
            "correlation": context.get("correlation"),
            "warnings": context.get("warnings"),
            "result_ids": list(minimal_evidence),
            "evidence_index": minimal_evidence,
        }
    return json_safe(context)


def _markdown_text(value) -> str:
    """Render untrusted data as text, not Markdown links, HTML or structure."""
    text = " ".join(str(value).split())
    text = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]<>#|!])", r"\\\1", text)


def _fmt(value) -> str:
    if value is None:
        return "not available"
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(item) for item in value)
    if isinstance(value, float):
        return f"{value:.6g}" if math.isfinite(value) else "not finite"
    return _markdown_text(value)


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
        f"- Python version: {_fmt((result.get('software') or {}).get('python'))}",
        "- Package versions: " + ", ".join(
            f"{_fmt(name)} {_fmt(version)}" for name, version in
            ((result.get("software") or {}).get("packages") or {}).items()
        ) if (result.get("software") or {}).get("packages") else "- Package versions: not recorded",
        f"- Source: {_fmt(source.get('name'))} ({_fmt(source.get('rows'))} rows, "
        f"{_fmt(len(source.get('columns') or []))} columns)",
        f"- Encoding / delimiter: {_fmt(source.get('encoding'))} / {_fmt(source.get('delimiter'))!r}",
        f"- SHA-256: `{_fmt(source.get('sha256'))}`",
        "",
        "## 1. Configuration",
        "",
        f"- X: {_fmt(roles.get('x'))}; Y: {_fmt(roles.get('y'))}",
        f"- X unit: {_fmt(roles.get('unit_x'))} (origin: {_fmt(roles.get('unit_x_origin'))}); "
        f"Y unit: {_fmt(roles.get('unit_y'))} (origin: {_fmt(roles.get('unit_y_origin'))})",
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
            f"- `{_markdown_text(column.get('name'))}`: missing={_fmt(column.get('missing'))}, "
            f"invalid={_fmt(column.get('invalid'))}, nonfinite={_fmt(column.get('nonfinite'))}, "
            f"coerced={_fmt(column.get('coerced'))}, valid={_fmt(column.get('valid'))}"
        )
    insights = result.get("insights") or {}
    if insights:
        lines += ["", "## Key insights (deterministic)", "", _markdown_text(insights.get("ranking")), ""]
        for card in insights.get("items") or []:
            lines += [f"### {_markdown_text(card.get('title'))}", "",
                      f"- {_markdown_text(card.get('label'))}: {_markdown_text(card.get('observation'))}",
                      f"- Interpretation: {_markdown_text(card.get('interpretation'))}",
                      f"- Evidence paths: {_fmt(card.get('evidence_paths'))}",
                      f"- Limitations: {_markdown_text(card.get('limitations'))}",
                      f"- Next step: {_markdown_text(card.get('next_step'))}",
                      f"- Why highlighted: {_markdown_text(card.get('rank_reason'))}", ""]
        if not insights.get("items"):
            lines += ["Insufficient information for supported insight cards.", ""]
        lines += [_markdown_text(insights.get("limitations")), ""]
    lines += ["", "## 3. Descriptive statistics", ""]
    for column, summary in stats.items():
        if not isinstance(summary, dict):
            continue
        lines += [
            f"### {_markdown_text(column)}",
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
            lines.append(f"| {_markdown_text(name)} | {_fmt(value)} | {_fmt(errors.get(name))} |")
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
    uncertainty = result.get("uncertainty") or {}
    if uncertainty:
        lines += ["", "### Conditional linear parameter confidence intervals", ""]
        if uncertainty.get("status") == "conditional":
            lines += [f"- Method: {_fmt(uncertainty.get('method'))}; confidence level: "
                      f"{_fmt(uncertainty.get('confidence_level'))}; residual df: "
                      f"{_fmt(uncertainty.get('degrees_of_freedom'))}", "",
                      "| Parameter | Estimate | Standard error | Lower | Upper | Unit |",
                      "| --- | ---: | ---: | ---: | ---: | --- |"]
            for item in uncertainty.get("parameters") or []:
                lines.append(f"| {_fmt(item.get('parameter'))} | {_fmt(item.get('estimate'))} | "
                             f"{_fmt(item.get('standard_error'))} | {_fmt(item.get('lower'))} | "
                             f"{_fmt(item.get('upper'))} | {_fmt(item.get('unit'))} |")
        else:
            lines.append(f"Unavailable: {_fmt(uncertainty.get('reason'))}")
        lines += ["", _markdown_text(uncertainty.get("assumptions")), "",
                  _markdown_text(uncertainty.get("limitations"))]
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
        lines.append(f"- Assumption: {_markdown_text(assumption)}")
    for item in domain.get("derived") or []:
        lines.append(f"- Computed: {_fmt(item.get('name'))} = {_fmt(item.get('value'))} "
                     f"{_fmt(item.get('unit') or '')} ({_fmt(item.get('source'))})")
    for hypothesis in domain.get("hypotheses") or []:
        lines.append(f"- {_markdown_text(hypothesis)}")
    for warning in domain.get("warnings") or []:
        lines.append(f"- Limitation: {_markdown_text(warning)}")

    lines += ["", "## 8. Figures", ""]
    for chart in result.get("visualizations") or []:
        lines.append(f"- {_fmt(chart.get('label'))}: {_fmt(chart.get('n_rows'))} rows plotted "
                     f"({_fmt(chart.get('file'))})")
        for warning in chart.get("warnings") or []:
            lines.append(f"  - Caution: {_markdown_text(warning)}")

    lines += ["", "## 9. Limitations and provenance", "",
              "- All numbers above were computed locally from the uploaded CSV; none were generated by an AI model.",
              "- Statistical confidence intervals describe sampling variability under stated assumptions, "
              "not instrument accuracy.",
              "- No measurement uncertainties are invented; error bars appear only when an uncertainty column is supplied.",
              "- Correlation and fitted coefficients do not establish causation.",
              "- Results outside the fitted X range are extrapolations."]
    for note in result.get("notes") or []:
        lines.append(f"- {_markdown_text(note)}")
    for warning in result.get("warnings") or []:
        lines.append(f"- {_markdown_text(warning)}")

    ai = result.get("ai")
    if ai:
        guard = ai.get("numeric_guard") or {}
        if guard:
            lines += ["", "### AI numerical check limitations", "", _markdown_text(guard.get("limitations"))]
        structured = ai.get("structured") or {}
        is_mock = bool(ai.get("is_mock") or ai.get("source") == "offline_mock")
        if is_mock:
            fit = result.get("fit") or {}
            parameters = fit.get("parameters") or {}
            metrics = fit.get("metrics") or {}

            computed_parameters = ", ".join(
                f"{name}={_fmt(value)}"
                for name, value in parameters.items()
            )

            lines += [
                "",
                "## 10. OFFLINE MOCK report (deterministic template, NOT AI)",
                "",
                f"Generator: {_fmt(ai.get('model'))}. This is a local deterministic template "
                "built from the computed context above. It is NOT a MuseSpark response, NOT "
                "an AI model output, and NOT experimental evidence. All numbers come from "
                "sections 1-9.",
                "",
            ]

            if computed_parameters:
                lines.append(f"Computed parameters: {computed_parameters}")

            # Use the Unicode escape for the squared symbol to avoid console encoding issues.
            r_squared_label = "R\u00b2"
            lines.append(
                f"Computed fit metrics: {r_squared_label}={_fmt(metrics.get('r2'))}; "
                f"RMSE={_fmt(metrics.get('rmse'))}; "
                f"n={_fmt(fit.get('n_observations'))}."
            )
            lines.append("")
        else:
            lines += ["", "## 10. AI-generated interpretation (unverified hypotheses)", "",
                      f"Provider model: {_fmt(ai.get('model'))}. The following text was generated by an AI "
                      "model from the computed context above. It is not experimental evidence and may be wrong.",
                      ""]
        ai_evidence = ai.get("evidence_index") or {}
        if ai_evidence:
            lines += ["", "### AI context evidence index (computed values)", "",
                      "IDs indicate the values sent to the provider; they do not verify the meaning of a claim.", ""]
            for identifier, values in ai_evidence.items():
                lines.append(f"- {_fmt(identifier)}: {_fmt(values)}")
            lines.append("")
        if ai.get("disclaimer"):
            lines += [f"> {_markdown_text(ai['disclaimer'])}", ""]
        for section in structured.get("sections") or []:
            lines += [f"### {_markdown_text(section.get('title'))}", "", _markdown_text(section.get("content", "")), ""]
        for i, claim in enumerate(structured.get("claims") or [], start=1):
            lines += [f"**Claim {i}** ({_fmt(claim.get('evidence_type'))}): {_markdown_text(claim.get('claim'))}",
                      f"- Evidence: {_markdown_text(claim.get('evidence'))}",
                      f"- Confidence/uncertainty: {_markdown_text(claim.get('confidence_or_uncertainty'))}",
                      f"- Limitation: {_markdown_text(claim.get('limitation'))}",
                      f"- Proposed verification: {_markdown_text(claim.get('proposed_verification'))}"]
            if claim.get("evidence_ids"):
                lines.append(f"- Computed result IDs: {', '.join(claim['evidence_ids'])}")
            lines.append("")
    else:
        lines += ["", "## 10. AI-generated interpretation", "",
                  "Not requested, or the provider was unavailable. All deterministic results above "
                  "are complete without AI."]
    propagation = result.get("propagation") or {}
    if propagation:
        supplied = propagation.get("inputs") or {}
        lines += ["", "## User-supplied uncertainty propagation (conditional)", "",
                  "Values and uncertainties below are user supplied, not measured or inferred by LabLens.",
                  f"- Equation: {_fmt(propagation.get('equation'))}",
                  f"- a: {_fmt(supplied.get('a'))}; standard uncertainty: {_fmt(supplied.get('u_a'))} "
                  f"{_fmt(supplied.get('unit_a'))}",
                  f"- b: {_fmt(supplied.get('b'))}; standard uncertainty: {_fmt(supplied.get('u_b'))} "
                  f"{_fmt(supplied.get('unit_b'))}",
                  f"- Computed value: {_fmt(propagation.get('value'))}; standard uncertainty: "
                  f"{_fmt(propagation.get('standard_uncertainty'))} {_fmt(propagation.get('unit'))}",
                  "", _markdown_text(propagation.get("method")), "", _markdown_text(propagation.get("assumptions")),
                  "", _markdown_text(propagation.get("limitations"))]
        if propagation.get("warning"):
            lines += ["", f"Warning: {_markdown_text(propagation['warning'])}"]
    comparison = result.get("comparison") or {}
    if comparison:
        lines += ["", "## Experiment comparison (user-confirmed, not independently verified)", "",
                  _markdown_text(comparison.get("method")), ""]
        for item in comparison.get("datasets") or []:
            lines.append(f"- {_fmt(item.get('dataset'))}: source {_fmt(item.get('source_name'))}; "
                         f"SHA-256 {_fmt(item.get('source_sha256'))}; X {_fmt(item.get('x_column'))} "
                         f"({_fmt(item.get('unit_x'))}); Y {_fmt(item.get('y_column'))} ({_fmt(item.get('unit_y'))}); "
                         f"paired n={_fmt(item.get('valid_pairs'))}; excluded={_fmt(item.get('excluded_pairs'))}; "
                         f"mean X={_fmt(item.get('mean_x'))}; mean Y={_fmt(item.get('mean_y'))}.")
        lines += ["", f"Difference in paired Y means, second minus first: "
                  f"{_fmt(comparison.get('mean_y_difference_second_minus_first'))} "
                  f"{_fmt((comparison.get('datasets') or [{}])[0].get('unit_y'))}.",
                  "", _markdown_text(comparison.get("limitations")), "", _markdown_text(comparison.get("plot_note"))]
    predictions = result.get("predictions") or {}
    if predictions:
        lines += ["", "## Follow-up predictions (model-based, not observations)", "",
                  _markdown_text(predictions.get("caveat")), "",
                  "| Candidate X | Predicted Y | Range |", "| --- | --- | --- |"]
        for row in predictions.get("rows") or []:
            lines.append(f"| {_fmt(row.get('candidate_x'))} | {_fmt(row.get('predicted_y'))} | "
                         f"{_fmt(row.get('range_flag'))} |")
        intervals = predictions.get("intervals") or {}
        if intervals.get("status") == "conditional":
            lines += ["", "### Conditional 95% intervals", "", _markdown_text(intervals.get("assumptions")),
                      "", _markdown_text(intervals.get("limitations")), "",
                      "| X | Mean lower | Mean upper | Prediction lower | Prediction upper | Range |",
                      "| --- | --- | --- | --- | --- | --- |"]
            for row in intervals.get("rows") or []:
                lines.append(f"| {_fmt(row.get('candidate_x'))} | {_fmt(row.get('mean_lower'))} | "
                             f"{_fmt(row.get('mean_upper'))} | {_fmt(row.get('prediction_lower'))} | "
                             f"{_fmt(row.get('prediction_upper'))} | {_fmt(row.get('range_flag'))} |")
        elif intervals:
            lines += ["", f"Prediction intervals unavailable: {_fmt(intervals.get('reason'))}."]
    research = result.get("research") or {}
    if research:
        context = research.get("context") or {}
        lines += ["", "## 11. Research context and offline learning", "",
                  "User-supplied context and assumptions are not independently verified; this is not AI output."]
        for key, label in (("title", "Title"), ("discipline", "Discipline"),
                           ("description", "Description"), ("apparatus", "Apparatus"),
                           ("conditions", "Conditions"), ("known_equation", "User-supplied equation"),
                           ("level", "Explanation level")):
            if context.get(key):
                lines.append(f"- {label}: {_fmt(context[key])}")
        for key, label in (("theory", "Theory and learning"), ("reliability", "Reliability and uncertainty")):
            block = research.get(key) or {}
            lines += ["", f"### {label}", ""]
            for note in block.get("notes") or []:
                lines.append(f"- {_markdown_text(note)}")
        chapter = research.get("chapter") or {}
        if chapter:
            lines += ["", "### Conditional theory chapter", ""]
            for item in chapter.get("missing") or []:
                lines.append(f"- Missing or unavailable: {_markdown_text(item)}")
            if chapter.get("symbols"):
                lines += ["", "| Symbol | Meaning | Unit | Origin |", "| --- | --- | --- | --- |"]
                for symbol in chapter["symbols"]:
                    lines.append(f"| {_fmt(symbol.get('symbol'))} | {_fmt(symbol.get('meaning'))} | "
                                 f"{_fmt(symbol.get('unit'))} | {_fmt(symbol.get('origin'))} |")
            for section in chapter.get("sections") or []:
                lines += ["", f"#### {_markdown_text(section.get('title'))}", ""]
                lines.extend(_markdown_text(paragraph) for paragraph in section.get("body") or [])
            derived = chapter.get("derived")
            if derived:
                lines += ["", f"Conditional resistance from fitted slope: {_fmt(derived.get('value'))} "
                          f"{_fmt(derived.get('unit'))}; unit conversion factor {_fmt(derived.get('conversion_factor'))}. "
                          "This model-based interpretation is not independently verified."]
        lines += ["", "External references were not retrieved or verified."]
    ledger = result.get("evidence_ledger") or {}
    if ledger:
        lines += ["", "## Evidence traceability (deterministic)", "",
                  f"Analysis fingerprint: `{_fmt(ledger.get('analysis_fingerprint'))}`", "",
                  _markdown_text(ledger.get("limitations")), ""]
        for link in ledger.get("insight_links") or []:
            lines.append(f"- Insight {_fmt(link.get('insight_id'))}: "
                         f"evidence {_fmt(link.get('evidence_ids'))}; unavailable {_fmt(link.get('missing_paths'))}.")
        lines += ["", "| Evidence ID | Type | Result path | Value |", "| --- | --- | --- | --- |"]
        for item in ledger.get("items") or []:
            lines.append(f"| {_fmt(item.get('id'))} | {_fmt(item.get('type'))} | "
                         f"{_fmt(item.get('result_path'))} | {_fmt(item.get('value'))} |")
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
        safe_name = safe_archive_name(name)
        if safe_name in files or safe_name == "manifest.json":
            raise ValueError("An additional artifact cannot replace a core export.")
        files[safe_name] = payload
    source, roles = result.get("source") or {}, result.get("roles") or {}
    cleaning, ai = result.get("cleaning") or {}, result.get("ai") or {}
    mode = ("mock" if ai.get("source") == "offline_mock" else
            "live" if ai.get("source") == "live_provider" else
            "unknown" if ai else "offline")
    manifest = {
        "manifest_version": "1.0", "generated_at_utc": result.get("generated_at_utc"),
        "dataset": {key: source.get(key) for key in ("sha256", "rows", "columns", "encoding", "delimiter", "data_origin")},
        "cleaning": {key: cleaning.get(key) for key in ("rows_in", "rows_out", "duplicates_removed", "invalid_pair_rows_excluded", "plan")},
        "configuration": {key: roles.get(key) for key in
                          ("x", "y", "group", "time", "uncertainty", "secondary_y", "unit_x", "unit_y", "model", "degree", "domain", "correlation_method")},
        "software": result.get("software"), "provider": {"mode": mode, "model": ai.get("model") if ai else None},
        "evidence_fingerprint": (result.get("evidence_ledger") or {}).get("analysis_fingerprint"),
        "artifacts": [{"name": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                      for name, payload in sorted(files.items())],
        "limitations": "Checksums detect changes, not authenticity. Manifest excludes its own hash and is not a complete environment lock.",
    }
    files["manifest.json"] = json.dumps(json_safe(manifest), ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8")
    return {safe_archive_name(name): payload for name, payload in files.items()}
