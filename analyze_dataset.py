"""General-purpose command-line analysis for delimited numeric datasets.

This is the CLI counterpart of ``general_app.py``. The original
``analyze_experiment.py`` remains available unchanged for the legacy
voltage-current sample workflow.

Examples
--------
    python analyze_dataset.py data/sample_voltage_current.csv \
        --x current_A --y voltage_V --model linear --output-dir results/run1

    python analyze_dataset.py data/examples/synthetic_calibration.csv \
        --x concentration_uM --y absorbance_570nm --uncertainty abs_sigma \
        --domain calibration --output-dir results/calibration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import ask_muse
import provider_config
from agent_core import AnalysisOrchestrator, OrchestratorConfig
from cleaning import apply_cleaning, build_plan, paired_values
from column_inference import infer_columns, suggest_roles
from data_io import DataImportError, read_csv_robust
from domain_modules import apply_domain
from fitting_core import MODEL_SPECS, compare_models, fit_model, suggest_models
from result_schema import ai_context, build_result, export_bundle, safe_archive_name
from statistics_core import (
    correlation,
    covariance,
    describe_numeric,
    descriptive_table,
    outlier_diagnostics,
)
from visualization_core import build_chart, render_png

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "results" / "general"
EXPORT_PLOTS = ("scatter", "histogram", "residuals", "distribution", "correlation_heatmap")


def analyze_csv(
    path,
    output_dir=None,
    *,
    x=None,
    y=None,
    model="linear",
    degree=2,
    uncertainty=None,
    group=None,
    time=None,
    domain="generic",
    unit_x="",
    unit_y="",
    correlation_method="pearson",
    remove_duplicates=False,
    generate_ai=False,
    section_titles=None,
    research_question=None,
    report_profile="legacy",
    generate_mock=False,
):
    """Run the full deterministic pipeline and write every export artifact.

    Returns the single result-schema dictionary. Raises ``ValueError`` for
    invalid local input/configuration so callers never see a traceback.
    """
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Could not read CSV: {source} does not exist.")
    try:
        load = read_csv_robust(source, source_name=source.name)
    except (DataImportError, ValueError, OSError) as exc:
        raise ValueError(f"Could not read CSV: {exc}") from None

    frame = load.frame
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("The dataset has no usable rows or columns.")
    profiles = infer_columns(frame)
    suggestion = suggest_roles(profiles)
    columns = [str(column) for column in frame.columns]

    x_col = x or suggestion.x or columns[0]
    y_col = y or suggestion.y or next((c for c in columns if c != x_col), None)
    if not y_col:
        raise ValueError("At least two columns are required; specify --x and --y.")
    if x_col not in columns or y_col not in columns:
        raise ValueError(f"Unknown column. Available columns: {', '.join(columns)}.")
    if x_col == y_col:
        raise ValueError("Choose different columns for --x and --y.")
    if model not in MODEL_SPECS:
        raise ValueError(f"Unknown model '{model}'. Choose from: {', '.join(MODEL_SPECS)}.")

    extra = [column for column in (x_col, y_col, uncertainty) if column]
    plan = build_plan(
        profiles, remove_duplicates=bool(remove_duplicates),
        x=x_col, y=y_col, extra_numeric=tuple(extra),
    )
    try:
        cleaned = apply_cleaning(frame, plan)
        x_values, y_values, _ = paired_values(cleaned, x_col, y_col)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Could not prepare selected columns as numeric: {exc}") from None
    if len(x_values) < 2:
        raise ValueError("At least two complete finite X/Y pairs are required for a fit.")

    weights = None
    if uncertainty:
        if uncertainty not in columns:
            raise ValueError(f"Unknown uncertainty column: {uncertainty}.")
        candidate = np.asarray(
            __import__("pandas").to_numeric(cleaned.working[uncertainty], errors="coerce"),
            dtype=float,
        )[cleaned.usable_pairs(x_col, y_col)]
        if len(candidate) == len(x_values) and np.all(np.isfinite(candidate)) and np.all(candidate > 0):
            weights = 1.0 / candidate**2
        else:
            raise ValueError(
                "The uncertainty column must contain finite positive 1-sigma values in every fitted row."
            )

    x_label = f"{x_col} ({unit_x})" if unit_x else x_col
    y_label = f"{y_col} ({unit_y})" if unit_y else y_col
    fit = fit_model(model, x_values, y_values, weights, degree=degree,
                    x_label=x_label, y_label=y_label)
    comparison = []
    for candidate_model in MODEL_SPECS:
        if candidate_model == model:
            comparison.append(fit)
            continue
        try:
            comparison.append(fit_model(candidate_model, x_values, y_values, weights,
                                        degree=degree, x_label=x_label, y_label=y_label))
        except Exception:
            pass

    numeric_columns = list(plan.numeric_columns)
    stats = {name: describe_numeric(cleaned.working[name]) for name in numeric_columns}
    stats_table = descriptive_table(cleaned.working, numeric_columns)
    corr = correlation(x_values, y_values, method=correlation_method)
    cov = covariance(x_values, y_values)
    outliers = outlier_diagnostics(y_values)
    domain_result = apply_domain(domain, fit, {
        "x": x_col, "y": y_col, "x_label": x_label, "y_label": y_label,
        "unit_x": unit_x, "unit_y": unit_y,
    })
    suggestions = suggest_models(x_values, y_values)

    chart_frame = cleaned.working.copy()
    for name in numeric_columns:
        companion = f"__numeric__{name}"
        if companion in chart_frame.columns:
            chart_frame[name] = chart_frame[companion]
    config = {
        "x": x_col, "y": y_col, "group": group, "time": time,
        "uncertainty": uncertainty, "secondary_y": [], "bins": 30,
        "fit_result": fit, "numeric_columns": numeric_columns,
        "correlation_method": correlation_method,
    }
    chart_files: dict[str, bytes] = {}
    chart_summaries = []
    for plot_type in EXPORT_PLOTS:
        spec = build_chart(plot_type, chart_frame, config)
        slug = plot_type.replace(" ", "_")
        if spec.valid:
            chart_files[f"plots/{slug}.html"] = spec.to_html().encode("utf-8")
            chart_files[f"plots/{slug}.png"] = render_png(plot_type, chart_frame, config)
        chart_summaries.append({
            "plot_type": plot_type, "label": spec.label, "n_rows": spec.n_rows,
            "file": f"plots/{slug}.png" if spec.valid else None,
            "warnings": spec.warnings, "notes": spec.notes,
            "reason": spec.reason if not spec.valid else None,
        })

    cleaning_dict = cleaned.report.as_dict()
    cleaning_dict["warnings"] = load.warnings + (
        ["Rows with invalid or missing X/Y are excluded from fitting but remain in cleaned_data.csv."]
        if cleaning_dict.get("invalid_pair_rows_excluded") else []
    )
    source_info = {
        "name": source.name, "sha256": load.sha256, "rows": len(frame),
        "columns": columns, "delimiter": load.delimiter,
        "encoding": load.encoding, "warnings": list(load.warnings),
        "duplicate_headers": list(load.duplicate_headers),
    }
    roles = {
        "x": x_col, "y": y_col, "group": group, "time": time,
        "uncertainty": uncertainty, "secondary_y": [],
        "unit_x": unit_x, "unit_y": unit_y, "unit_time": "",
        "unit_x_origin": "user_entered" if unit_x else "unspecified",
        "unit_y_origin": "user_entered" if unit_y else "unspecified",
        "question": research_question or "Command-line analysis",
        "model": model, "degree": degree,
        "domain": domain, "correlation_method": correlation_method,
        "inferred_x": suggestion.x, "inferred_y": suggestion.y,
    }
    result = build_result(
        source=source_info, roles=roles, cleaning=cleaning_dict, statistics=stats,
        correlation={**corr, "covariance": cov}, outliers=outliers, fit=fit,
        model_comparison=compare_models(comparison),
        model_suggestions=suggestions, domain=domain_result,
        chart_summaries=chart_summaries,
        notes=["Generated by analyze_dataset.py (CLI)."],
    )

    if generate_ai or generate_mock:
        context = ai_context(result, research_question=research_question)
        titles = (list(section_titles) if section_titles else
                  list(ask_muse.resolve_section_titles(None, profile=report_profile)))
        try:
            if generate_mock:
                # Explicit opt-in only: this is NEVER a substitute for a live AI response.
                wrapper = ask_muse.generate_mock_report(
                    context, section_titles=titles, profile=report_profile,
                    research_question=research_question,
                )
            elif not provider_config.get_api_key():
                result["ai_note"] = ("AI was requested but BASETEN_API_KEY is not configured; "
                                     "deterministic analysis is complete. Use --ai-mock for a "
                                     "clearly labelled offline preview.")
                wrapper = None
            elif report_profile == ask_muse.DEFAULT_REPORT_PROFILE:
                wrapper = ask_muse.generate_interpretation(context, section_titles=titles)
            else:
                wrapper = ask_muse.generate_interpretation(
                    context, section_titles=titles, profile=report_profile
                )
            if wrapper is not None:
                wrapper = ask_muse.enforce_report_provenance(
                    wrapper, "mock" if generate_mock else "live"
                )
                structured = ask_muse.validate_report(
                    wrapper.get("structured"), titles, profile=report_profile,
                    allowed_evidence_ids=context.get("result_ids"),
                )
                if structured is None:
                    result["ai_note"] = "The report was invalid locally and was rejected."
                else:
                    result["ai"] = {**wrapper, "structured": structured}
        except (ValueError, RuntimeError) as exc:
            result["ai_note"] = f"AI interpretation unavailable: {type(exc).__name__}."

    destination = Path(output_dir) if output_dir else DEFAULT_OUTPUT
    destination.mkdir(parents=True, exist_ok=True)
    exports = export_bundle(result, cleaned_frame=cleaned.working,
                            descriptive_table=stats_table, charts=chart_files)
    for name, payload in exports.items():
        target = destination / safe_archive_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return result


def build_parser():
    parser = argparse.ArgumentParser(
        description="General-purpose scientific CSV analysis (delimited text only).",
    )
    parser.add_argument("csv", help="Path to a .csv/.tsv/.txt delimited file.")
    parser.add_argument("--x", help="Independent-variable column (default: inferred).")
    parser.add_argument("--y", help="Dependent-variable column (default: inferred).")
    parser.add_argument("--model", default="linear", choices=list(MODEL_SPECS))
    parser.add_argument("--degree", type=int, default=2, help="Polynomial degree (1-6).")
    parser.add_argument("--uncertainty", help="Column of 1-sigma uncertainties for weighted fitting.")
    parser.add_argument("--group", help="Optional group/category column.")
    parser.add_argument("--time", help="Optional time column.")
    parser.add_argument("--domain", default="generic",
                        choices=["generic", "ohmic", "calibration", "growth"])
    parser.add_argument("--unit-x", default="")
    parser.add_argument("--unit-y", default="")
    parser.add_argument("--correlation-method", default="pearson", choices=["pearson", "spearman"])
    parser.add_argument("--remove-duplicates", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--ai", action="store_true", help="Request an optional Muse Spark report.")
    parser.add_argument("--agent", action="store_true",
                        help="Also run the bounded analysis agent and write its audit trail.")
    parser.add_argument("--agent-use-ai", action="store_true",
                        help="Let Muse Spark propose the agent plan (requires BASETEN_API_KEY).")
    parser.add_argument("--question", help="Research question included in AI context and agent audit (max 300 chars).")
    parser.add_argument("--agent-question", help="Override the agent's research question.")
    parser.add_argument("--report-profile", default="legacy",
                        choices=list(ask_muse.REPORT_PROFILES),
                        help="Strict report schema profile (legacy is the default).")
    parser.add_argument("--section", action="append", dest="sections",
                        help="Report section title (repeatable; must belong to the selected profile).")
    parser.add_argument("--ai-mock", action="store_true",
                        help="Write an explicitly labelled deterministic OFFLINE MOCK report (no API key, no network).")
    return parser


def run_agent(path, output_dir, *, use_ai: bool = False,
              research_question: str | None = None) -> dict:
    """Run the bounded agent on the same input and write audit artifacts."""
    load = read_csv_robust(Path(path), source_name=Path(path).name)
    run = AnalysisOrchestrator(OrchestratorConfig(
        use_ai=use_ai, research_question=research_question,
    )).run(load)
    destination = Path(output_dir) / "agent"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "agent_audit.json").write_bytes(run.to_json_bytes())
    (destination / "agent_events.jsonl").write_bytes(run.to_jsonl())
    (destination / "agent_report.md").write_text(run.to_markdown(), encoding="utf-8")
    data = run.to_dict()
    return {"state": data["final"]["state"], "plan_source": data["plan_source"],
            "steps": data["totals"]["steps"], "retries": data["totals"]["retries"],
            "directory": str(destination)}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = analyze_csv(
            args.csv, args.output_dir, x=args.x, y=args.y, model=args.model,
            degree=args.degree, uncertainty=args.uncertainty, group=args.group,
            time=args.time, domain=args.domain, unit_x=args.unit_x,
            unit_y=args.unit_y, correlation_method=args.correlation_method,
            remove_duplicates=args.remove_duplicates, generate_ai=args.ai,
            section_titles=args.sections, research_question=args.question,
            report_profile=args.report_profile, generate_mock=args.ai_mock,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: analysis failed ({type(exc).__name__}).", file=sys.stderr)
        return 2
    fit = result.get("fit") or {}
    print(f"Source: {result['source']['name']} ({result['source']['rows']} rows)")
    print(f"X: {result['roles']['x']}  Y: {result['roles']['y']}  Model: {result['roles']['model']}")
    print(f"Fit successful: {fit.get('success')}  n = {fit.get('n_observations')}")
    if fit.get("success"):
        print(f"Equation: {fit.get('equation')}")
        print(f"R2: {fit.get('metrics', {}).get('r2')}")
    else:
        print(f"Reason: {fit.get('reason')}")
    if result.get("ai_note"):
        print(result["ai_note"])
    if (result.get("ai") or {}).get("is_mock"):
        print("OFFLINE MOCK report written (deterministic template, NOT Muse Spark, NOT AI).")
    if args.agent:
        use_ai = bool(args.agent_use_ai and provider_config.get_api_key())
        try:
            agent_summary = run_agent(
                args.csv, args.output_dir, use_ai=use_ai,
                research_question=args.agent_question or args.question,
            )
        except Exception as exc:
            print(f"Error: agent failed ({type(exc).__name__}).", file=sys.stderr)
            return 2
        print(f"Agent state: {agent_summary['state']} | plan: {agent_summary['plan_source']} "
              f"| steps: {agent_summary['steps']} | retries: {agent_summary['retries']}")
        print(f"Agent audit: {agent_summary['directory']}")
    print(f"Artifacts written to: {Path(args.output_dir).resolve()}")
    print(json.dumps({"schema_version": result["schema_version"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
