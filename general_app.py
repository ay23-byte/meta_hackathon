"""LabLens AI - general-purpose scientific CSV analysis workspace.

Steps A-G: Upload, Validate/Clean, Configure, Explore, Fit, Interpret, Export.
The bundled voltage-current sample is offered as one example dataset, never
as the only supported workflow. Column names, units, model, domain layer and
report sections are all user-controlled.

Run with:  streamlit run general_app.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import ask_muse
import provider_config
from agent_core import AnalysisOrchestrator, OrchestratorConfig
from cleaning import apply_cleaning, build_plan, paired_values, preview_cleaning
from column_inference import infer_columns, suggest_roles
from data_io import DataImportError, read_csv_robust
from domain_modules import apply_domain, list_domain_modules
from fitting_core import (
    MODEL_SPECS,
    compare_models,
    fit_model,
    predict_with_flags,
    suggest_models,
)
from result_schema import (
    ai_context,
    build_result,
    export_bundle,
    markdown_report,
    safe_archive_name,
)
from statistics_core import (
    correlation,
    covariance,
    describe_numeric,
    descriptive_table,
    outlier_diagnostics,
)
from visualization_core import PLOT_TYPES, build_chart, render_png

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "data" / "sample_voltage_current.csv"
EXAMPLES = sorted((ROOT / "data" / "examples").glob("*.csv")) if (ROOT / "data" / "examples").exists() else []

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SOURCE_ROWS = 200_000
MAX_CANDIDATE_VALUES = 50
MAX_SHORT_TEXT = 300
MAX_UNIT_TEXT = 24
MAX_CANDIDATE_TEXT = 2000
MAX_PLOTS_EXPORTED = 4

st.set_page_config(page_title="LabLens AI · General analysis", page_icon="🔬", layout="wide")


# ---------------------------------------------------------------------------
# Cached, deterministic computations
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, max_entries=6)
def load_dataset(raw: bytes, name: str):
    return read_csv_robust(
        io.BytesIO(raw), source_name=name,
        max_bytes=MAX_UPLOAD_BYTES, max_rows=MAX_SOURCE_ROWS,
    )


@st.cache_data(show_spinner=False, max_entries=6)
def profile_dataset(raw: bytes, name: str):
    load = load_dataset(raw, name)
    return infer_columns(load.frame)


@st.cache_data(show_spinner=False, max_entries=6)
def fit_cached(model: str, x_bytes: bytes, y_bytes: bytes, w_bytes: bytes | None,
               degree: int, x_label: str, y_label: str):
    """Fit on arrays passed as bytes so the result is cacheable."""
    x = np.frombuffer(x_bytes, dtype=float)
    y = np.frombuffer(y_bytes, dtype=float)
    weights = np.frombuffer(w_bytes, dtype=float) if w_bytes is not None else None
    return fit_model(model, x, y, weights, degree=degree, x_label=x_label, y_label=y_label)


def unit_text(value, fallback=""):
    text = "".join(ch for ch in str(value or "") if ch.isalnum() or ch in "_./^-°µΩ ")
    text = text.strip()[:MAX_UNIT_TEXT]
    return text or fallback


def _hash(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, allow_nan=False, default=str).encode("utf-8")
    ).hexdigest()


def _safe_error(exc: Exception) -> str:
    """Never print a traceback to the UI; never echo an API key."""
    message = " ".join(str(exc).split())[:MAX_SHORT_TEXT]
    safe = provider_config.redact(f"{type(exc).__name__}: {message}" if message
                                  else type(exc).__name__)
    return safe


def step_header(letter: str, title: str, caption: str):
    st.subheader(f"{letter} · {title}")
    st.caption(caption)


# ---------------------------------------------------------------------------
# Sidebar / provenance
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("LabLens AI")
    st.caption("Built with Muse Spark Open · Optional AI via https://inference.baseten.co/v1")
    provider = ask_muse.provider_status()
    if provider["api_key_configured"]:
        st.info(f"Muse Spark key configured. Model: {provider['model']}. "
                "Live reachability is NOT verified until a report is requested.")
    else:
        st.info("Muse Spark key not configured — deterministic analysis, exports and the "
                "labelled offline MOCK report still work.")
    with st.expander("Provider status (honest configuration check)"):
        st.json({key: provider[key] for key in (
            "provider", "base_url", "model", "api_key_configured", "key_source",
            "env_file_present", "mode", "live_call_attempted", "live_verified",
            "offline_mock_available", "max_transient_retries",
        )})
        st.caption(provider["message"])
    if st.checkbox("Show optional provider connectivity check", value=False):
        st.caption("Sends one minimal request without dataset context; it may consume credits. "
                   "It does not verify structured report generation.")
        if st.button("Check provider connectivity", key="provider_connectivity"):
            try:
                with st.spinner("Checking provider connectivity..."):
                    ask_muse.check_provider_connectivity()
            except (RuntimeError, ValueError) as exc:
                st.session_state["provider_check_result"] = ("failed", _safe_error(exc))
            else:
                st.session_state["provider_check_result"] = ("succeeded", "A non-empty response was received. Structured reports were not tested.")
        check = st.session_state.get("provider_check_result")
        if check:
            if check[0] == "succeeded":
                st.success(f"Connectivity check succeeded: {check[1]}")
            else:
                st.error(f"Connectivity check failed: {check[1]}")
    st.markdown("**Workflow**")
    for letter, label in (
        ("A", "Upload"), ("B", "Validate / Clean"), ("C", "Configure"),
        ("D", "Explore"), ("E", "Fit"), ("F", "Interpret"), ("G", "Export"),
    ):
        st.caption(f"{letter} · {label}")
    st.caption(
        "Supported input: delimited text/CSV only (.csv, .tsv, .txt). "
        "Excel, JSON, HDF5 and binary instrument formats are not supported."
    )
    st.caption(f"Python {sys.version.split()[0]} · pandas {pd.__version__} · Streamlit {st.__version__}")

st.title("LabLens AI - general scientific data analysis")
st.caption(
    "Upload any delimited numeric dataset, choose the columns and model yourself, "
    "and export a fully reproducible record. Nothing is assumed about your scientific domain."
)
with st.expander("First time here? Quick start"):
    st.markdown(
        "1. Upload a `.csv`, `.tsv` or `.txt` file, or choose a bundled synthetic example.\n"
        "2. Review validation/cleaning, then set X, Y, units and the model.\n"
        "3. Read the computed statistics, plots and fit diagnostics.\n"
        "4. Export CSV / JSON / ZIP. Live AI needs a key and an explicit button press; "
        "the bounded agent needs its own consent checkbox."
    )


# ---------------------------------------------------------------------------
# A · Upload
# ---------------------------------------------------------------------------

step_header("A", "Upload", "Delimiter, encoding, duplicate headers and size are detected before parsing.")

upload_col, example_col = st.columns([3, 2])
with upload_col:
    uploaded = st.file_uploader(
        "Upload a delimited text file", type=["csv", "tsv", "txt"],
        help=f"Maximum {MAX_UPLOAD_BYTES // 1024 // 1024} MiB and {MAX_SOURCE_ROWS:,} rows.",
    )
with example_col:
    example_name = st.selectbox(
        "Or load a bundled synthetic example",
        ["(use upload)" if uploaded else "Original voltage-current sample"]
        + [path.name for path in EXAMPLES],
        index=0,
    )

if uploaded is not None:
    raw = uploaded.getvalue()
    source_name = uploaded.name
else:
    if example_name == "(use upload)":
        st.info("Upload a file or choose a bundled example to begin.")
        st.stop()
    chosen = SAMPLE if example_name == "Original voltage-current sample" else next(
        (path for path in EXAMPLES if path.name == example_name), SAMPLE
    )
    raw = chosen.read_bytes()
    source_name = chosen.name

if not raw:
    st.error("The selected file is empty.")
    st.stop()
if len(raw) > MAX_UPLOAD_BYTES:
    st.error(f"{source_name} exceeds the {MAX_UPLOAD_BYTES:,}-byte limit. Upload a smaller CSV.")
    st.stop()

try:
    load = load_dataset(raw, source_name)
except (DataImportError, ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(f"Could not import {source_name}: {_safe_error(exc)}")
    st.stop()
except Exception as exc:
    st.error(f"Could not import {source_name}: {_safe_error(exc)}")
    st.stop()

frame = load.frame
if frame.empty or len(frame.columns) == 0:
    st.error("The dataset has no usable rows or columns. Upload a CSV with a header and at least one row.")
    st.stop()
if len(frame) > MAX_SOURCE_ROWS:
    st.error(f"The dataset exceeds the {MAX_SOURCE_ROWS:,}-row limit. Downsample before uploading.")
    st.stop()

st.caption(
    f"`{source_name}` · {len(frame):,} rows · {len(frame.columns)} columns · "
    f"delimiter `{load.delimiter!r}` · encoding `{load.encoding}` · "
    f"SHA-256 `{load.sha256[:16]}…`"
)
for warning in load.warnings:
    st.warning(warning)
st.dataframe(frame.head(8), width="stretch", hide_index=True)

profiles = profile_dataset(raw, source_name)
suggestion = suggest_roles(profiles)
all_columns = [str(column) for column in frame.columns]


# ---------------------------------------------------------------------------
# B · Validate / Clean
# ---------------------------------------------------------------------------

step_header("B", "Validate / Clean", "Column types are inferred from data shape. Missing, invalid and non-finite values are counted separately.")

profile_rows = [
    {
        "Column": p.name, "Kind": p.kind, "Rows": p.n_total,
        "Valid numeric": p.n_valid, "Missing": p.n_missing,
        "Invalid": p.n_invalid, "Non-finite": p.n_nonfinite,
        "Distinct": p.n_unique, "Why": "; ".join(p.reasons)[:160],
    }
    for p in profiles
]
st.dataframe(pd.DataFrame(profile_rows), width="stretch", hide_index=True)
if suggestion.notes:
    st.info(" · ".join(suggestion.notes))

with st.expander("Cleaning options and preview", expanded=True):
    inferred_numeric = [p.name for p in profiles if p.is_numeric]
    numeric_override = st.multiselect(
        "Columns to treat as numeric", options=all_columns,
        default=inferred_numeric,
        help="Add a mixed column here if it contains measurements with a few typos.",
    )
    remove_duplicates = st.checkbox("Remove exact duplicate rows", value=False)
    consent = st.checkbox(
        "I have reviewed the preview — apply these cleaning choices to the analysis", value=True,
        help="Unchecking this keeps duplicate rows and disables invalid-pair exclusion; "
             "a numeric fit still cannot use non-finite values.",
    )
    effective_duplicates = remove_duplicates and consent
    plan = build_plan(
        profiles, remove_duplicates=effective_duplicates,
        exclude_invalid_pairs=consent, extra_numeric=tuple(numeric_override),
    )
    report = preview_cleaning(frame, plan)
    st.dataframe(pd.DataFrame(report.as_dict()["columns"]), width="stretch", hide_index=True)
    st.caption(
        f"Rows in: {report.n_rows_in:,} · rows out: {report.n_rows_out:,} · "
        f"duplicates removed: {report.n_duplicates_removed:,} · "
        f"cells coerced to numeric: {report.n_cells_changed:,}"
    )
    for note in report.notes:
        st.caption(f"• {note}")
    if not consent:
        st.warning(
            "Cleaning consent is off: duplicate rows are retained and no rows are excluded "
            "by this step. Numeric fitting still ignores non-finite values by necessity."
        )


# ---------------------------------------------------------------------------
# C · Configure
# ---------------------------------------------------------------------------

step_header("C", "Configure", "Role hints are suggestions only; your choices determine the analysis.")

role_col, model_col, unit_col = st.columns(3)
with role_col:
    def choose(label, options, default, *, allow_none=True):
        values = (["(none)"] if allow_none else []) + [str(item) for item in options]
        wanted = str(default) if default in values else ("(none)" if allow_none else values[0])
        chosen = st.selectbox(label, values, index=values.index(wanted))
        return None if chosen == "(none)" else chosen

    x_col = choose("X column (independent)", all_columns, suggestion.x or all_columns[0], allow_none=False)
    y_options = [column for column in numeric_override if column != x_col]
    y_col = choose("Y column (dependent)", y_options, suggestion.y, allow_none=False)
    group_col = choose("Group / category column", all_columns, suggestion.group)
    time_col = choose("Time column", all_columns, suggestion.time)
    uncertainty_col = choose("Uncertainty column (1 sigma)", all_columns, suggestion.uncertainty)
    secondary_y = st.multiselect(
        "Secondary Y columns (plotted separately)",
        [column for column in numeric_override if column not in (x_col, y_col)],
        default=[],
    )
with model_col:
    model_name = st.selectbox("Model", list(MODEL_SPECS), format_func=lambda key: MODEL_SPECS[key]["label"])
    degree = st.slider("Polynomial degree", 1, 6, 2) if model_name == "polynomial" else 2
    domain_id = st.selectbox(
        "Domain interpretation layer", [module["id"] for module in list_domain_modules()],
        format_func=lambda key: next(m["label"] for m in list_domain_modules() if m["id"] == key),
    )
    correlation_method = st.selectbox("Correlation method", ["pearson", "spearman"])
    plot_type = st.selectbox("Primary chart", list(PLOT_TYPES), format_func=lambda key: PLOT_TYPES[key])
    bins = st.slider("Histogram bins", 5, 100, 30)
with unit_col:
    default_x_unit = "A" if "current" in str(x_col).casefold() else ""
    default_y_unit = "V" if "voltage" in str(y_col).casefold() else ""
    unit_x = unit_text(st.text_input("X unit (optional)", value=default_x_unit, max_chars=MAX_UNIT_TEXT))
    unit_y = unit_text(st.text_input("Y unit (optional)", value=default_y_unit, max_chars=MAX_UNIT_TEXT))
    unit_time = unit_text(st.text_input("Time unit (optional)", value="", max_chars=MAX_UNIT_TEXT))
    question = st.text_input("Scientific question", value="How does Y vary with X?", max_chars=MAX_SHORT_TEXT)[:MAX_SHORT_TEXT]
    candidate_text = st.text_input(
        "Candidate current values" if source_name == SAMPLE.name else f"Candidate {x_col} values",
        value="", max_chars=MAX_CANDIDATE_TEXT,
        help="Comma-separated numeric X values for model-based predictions.",
    )

st.caption(
    f"Selected model: {MODEL_SPECS[model_name]['label']} — {MODEL_SPECS[model_name]['assumptions']}"
)
domain_meta = next(module for module in list_domain_modules() if module["id"] == domain_id)
with st.expander("Domain assumptions (read before interpreting)"):
    st.write(domain_meta["description"])
    for assumption in domain_meta["assumptions"]:
        st.caption(f"• {assumption}")
if secondary_y:
    st.warning(
        "Secondary Y columns are exported as separate charts, not overlaid on a second axis: "
        "dual axes can imply relationships that depend only on scale choices."
    )

report_profile = st.selectbox(
    "AI report profile", list(ask_muse.REPORT_PROFILES),
    index=list(ask_muse.REPORT_PROFILES).index(ask_muse.DEFAULT_REPORT_PROFILE),
    format_func=lambda key: {
        "legacy": "Legacy eight-section report (default)",
        "scientific": "Scientific report (research question, methods, fit, next steps)",
    }[key],
    help="Both profiles use the same strict schema. The legacy profile preserves the original eight titles.",
)
section_registry = ask_muse.section_registry(report_profile)
default_titles = list(ask_muse.resolve_section_titles(None, profile=report_profile))
section_options = list(section_registry)
selected_sections = st.multiselect(
    "AI report sections (optional)", section_options,
    default=default_titles,
    help=f"A maximum of {len(section_options)} registered sections is allowed. "
         "Unknown or duplicate names are rejected.",
)
if not selected_sections:
    st.info(f"No AI sections selected; the profile's {len(default_titles)} default sections will be used.")
effective_titles = list(selected_sections) if selected_sections else default_titles


# ---------------------------------------------------------------------------
# Deterministic pipeline (no Streamlit calls inside)
# ---------------------------------------------------------------------------

try:
    final_plan = build_plan(
        profiles,
        remove_duplicates=effective_duplicates,
        exclude_invalid_pairs=consent,
        x=x_col, y=y_col,
        extra_numeric=tuple(dict.fromkeys([*numeric_override, x_col or "", y_col or "",
                                           uncertainty_col or ""])),
    )
    cleaning_result = apply_cleaning(frame, final_plan)
    working = cleaning_result.working
    x_values, y_values, source_rows = paired_values(cleaning_result, x_col, y_col)
except (ValueError, KeyError, TypeError) as exc:
    st.error(f"Configuration error: {_safe_error(exc)}")
    st.stop()
except Exception as exc:
    st.error(f"Could not prepare the analysis: {_safe_error(exc)}")
    st.stop()

if x_col == y_col:
    st.error("Choose different columns for X and Y.")
    st.stop()
if len(x_values) < 2:
    st.error(
        f"At least two complete finite rows are required for the selected X/Y pair "
        f"({len(x_values)} available). Check the cleaning preview and column roles."
    )
    st.stop()

# Weighting: only when a user-selected uncertainty column exists.
uncertainty_values = None
if uncertainty_col and uncertainty_col in working.columns:
    candidate_unc = np.asarray(
        pd.to_numeric(working[uncertainty_col], errors="coerce"), dtype=float
    )
    usable = cleaning_result.usable_pairs(x_col, y_col)
    if len(candidate_unc) == len(usable):
        aligned = candidate_unc[usable]
        if np.all(np.isfinite(aligned)) and np.all(aligned > 0) and len(aligned) == len(x_values):
            uncertainty_values = aligned
        else:
            st.warning(
                "The selected uncertainty column contains non-positive or non-finite values "
                "in fitted rows, so it is NOT used as weights. No uncertainties were invented."
            )

# Fit the chosen model plus a bounded comparison set.
x_label = f"{x_col}" + (f" ({unit_x})" if unit_x else "")
y_label = f"{y_col}" + (f" ({unit_y})" if unit_y else "")
try:
    x_bytes = np.ascontiguousarray(x_values, dtype=float).tobytes()
    y_bytes = np.ascontiguousarray(y_values, dtype=float).tobytes()
    # The selected column is a 1-sigma uncertainty; fitting_core expects
    # inverse-variance weights w = 1/sigma**2.
    w_bytes = (np.ascontiguousarray(1.0 / uncertainty_values**2, dtype=float).tobytes()
               if uncertainty_values is not None else None)
    fit = fit_cached(model_name, x_bytes, y_bytes, w_bytes, degree, x_label, y_label)
except Exception as exc:
    st.error(f"The fit could not be computed: {_safe_error(exc)}")
    st.stop()

comparison_results = []
candidate_models = ["linear", "polynomial", "exponential", "logarithmic", "power"]
if len(x_values) > 5000:
    candidate_models = ["linear", "polynomial"]
for candidate in candidate_models:
    if candidate == model_name:
        comparison_results.append(fit)
        continue
    try:
        comparison_results.append(
            fit_cached(candidate, x_bytes, y_bytes, w_bytes, degree, x_label, y_label)
        )
    except Exception:
        pass

try:
    model_table = compare_models(comparison_results)
    suggestions = suggest_models(x_values, y_values)

    stats_columns = list(dict.fromkeys(
        [column for column in numeric_override if column] + [x_col, y_col]
        + ([uncertainty_col] if uncertainty_col else [])
    ))
    stats_columns = [column for column in stats_columns if column in working.columns]
    stats = {
        column: describe_numeric(working[column])
        for column in stats_columns
    }
    stats_table = descriptive_table(working, stats_columns)
    corr_result = correlation(x_values, y_values, method=correlation_method)
    cov_result = covariance(x_values, y_values)
    outliers = outlier_diagnostics(y_values)

    domain = apply_domain(domain_id, fit, {
        "x": x_col, "y": y_col, "x_label": x_label, "y_label": y_label,
        "unit_x": unit_x, "unit_y": unit_y, "unit_time": unit_time,
    })

    chart_config = {
        "x": x_col, "y": y_col, "group": group_col, "time": time_col,
        "uncertainty": uncertainty_col, "secondary_y": secondary_y,
        "bins": bins, "fit_result": fit, "numeric_columns": numeric_override,
        "correlation_method": correlation_method,
    }
    # Use companion numeric columns where available so arbitrary headers work.
    chart_frame = working.copy()
    for column in stats_columns:
        companion = f"__numeric__{column}"
        if companion in chart_frame.columns:
            chart_frame[column] = chart_frame[companion]
    chart_spec = build_chart(plot_type, chart_frame, chart_config)
except Exception as exc:
    st.error(f"Could not compute statistics or charts: {_safe_error(exc)}")
    st.stop()

export_chart_types = [plot_type]
for extra in ("scatter", "histogram", "residuals", "distribution", "correlation_heatmap"):
    if extra != plot_type and len(export_chart_types) < MAX_PLOTS_EXPORTED:
        export_chart_types.append(extra)

chart_summaries = []
chart_files: dict[str, bytes] = {}
for chart_name in export_chart_types:
    try:
        built = chart_spec if chart_name == plot_type else build_chart(chart_name, chart_frame, chart_config)
        slug = chart_name.replace(" ", "_")
        if built.valid:
            chart_files[f"plots/{slug}.html"] = built.to_html().encode("utf-8")
            chart_files[f"plots/{slug}.png"] = render_png(chart_name, chart_frame, chart_config)
        chart_summaries.append({
            "plot_type": chart_name, "label": built.label, "n_rows": built.n_rows,
            "file": f"plots/{slug}.png" if built.valid else None,
            "warnings": built.warnings, "notes": built.notes,
            "reason": built.reason if not built.valid else None,
        })
    except Exception as exc:
        chart_summaries.append({"plot_type": chart_name, "label": chart_name,
                                "n_rows": 0, "file": None,
                                "warnings": [_safe_error(exc)], "notes": [], "reason": _safe_error(exc)})

cleaning_dict = cleaning_result.report.as_dict()
cleaning_dict["warnings"] = ([
    "Rows with invalid or missing X/Y are excluded from fitting but remain in the cleaned CSV."
] if cleaning_dict.get("invalid_pair_rows_excluded") else [])
source_info = {
    "name": source_name, "sha256": load.sha256, "rows": len(frame),
    "columns": all_columns, "delimiter": load.delimiter,
    "encoding": load.encoding, "warnings": list(load.warnings),
    "duplicate_headers": list(load.duplicate_headers),
}
roles = {
    "x": x_col, "y": y_col, "group": group_col, "time": time_col,
    "uncertainty": uncertainty_col, "secondary_y": list(secondary_y),
    "unit_x": unit_x, "unit_y": unit_y, "unit_time": unit_time,
    "question": question, "model": model_name, "degree": degree,
    "domain": domain_id, "correlation_method": correlation_method,
}
try:
    result = build_result(
        source=source_info, roles=roles, cleaning=cleaning_dict, statistics=stats,
        correlation=corr_result, outliers=outliers, fit=fit,
        model_comparison=model_table, model_suggestions=suggestions,
        domain=domain, chart_summaries=chart_summaries,
        notes=[
            "Cleaned CSV keeps the original columns and adds __numeric__ companion columns.",
            f"Weighted fitting was {'enabled' if uncertainty_values is not None else 'not enabled'}.",
            "Interactive HTML plots load Vega-Lite from a CDN; PNG plots are rendered locally.",
        ],
    )
    context = ai_context(result, research_question=question)
    context_hash = _hash({
        "result": {key: result[key] for key in (
            "source", "roles", "cleaning", "statistics", "correlation", "outliers",
            "fit", "model_comparison", "domain", "warnings",
        )},
        "sections": effective_titles,
        "profile": report_profile,
        "question": question,
        "result_ids": context.get("result_ids"),
        "model": ask_muse.MODEL,
    })
except Exception as exc:
    st.error(f"Could not assemble the result record: {_safe_error(exc)}")
    st.stop()
# Track the analysis hash separately: a failed live request may clear the
# report state, but a later context change must still clear stale errors and
# in-flight flags. Both live and mock reports are invalidated together.
stored_ai_hash = st.session_state.get("ai_context_hash")
if stored_ai_hash != context_hash:
    st.session_state.pop("ai_state", None)
    st.session_state.pop("ai_last_error", None)
    st.session_state.pop("ai_request_in_flight", None)
    st.session_state["ai_context_hash"] = context_hash
else:
    ai_state = st.session_state.get("ai_state")
    if isinstance(ai_state, dict) and ai_state.get("hash") != context_hash:
        st.session_state.pop("ai_state", None)
result["ai"] = None


# ---------------------------------------------------------------------------
# D · Explore
# ---------------------------------------------------------------------------

step_header("D", "Explore", "Descriptive statistics, association, outlier diagnostics and charts from your chosen columns.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows uploaded", f"{len(frame):,}")
m2.metric("Complete X/Y pairs", f"{len(x_values):,}")
m3.metric("Rows excluded from fit", f"{cleaning_dict.get('invalid_pair_rows_excluded', 0):,}")
m4.metric("Numeric columns", f"{len(numeric_override):,}")

with st.expander("Descriptive statistics", expanded=True):
    st.dataframe(stats_table, width="stretch", hide_index=True)
    st.caption(
        "Sample SD uses ddof=1. The 95% t interval describes uncertainty of the mean under "
        "independent, approximately normal observations — not instrument accuracy."
    )
assoc_col, outlier_col = st.columns(2)
with assoc_col:
    st.write("**Association**")
    if corr_result.get("valid"):
        st.write(f"{corr_result['method'].capitalize()} r = {corr_result['coefficient']:.6g} "
                 f"(n = {corr_result['n_valid']}, p = {corr_result['p_value']:.4g})")
        st.caption(corr_result.get("caveat", ""))
    else:
        st.caption(corr_result.get("reason", "Correlation unavailable."))
    if cov_result.get("valid"):
        st.caption(f"Sample covariance (ddof={cov_result['ddof']}) = {cov_result['value']:.6g}")
with outlier_col:
    st.write("**Outlier diagnostics (IQR fences)**")
    if outliers.get("valid"):
        st.write(f"Flagged {outliers['n_low']} low and {outliers['n_high']} high of "
                 f"{outliers['n_valid']} finite Y values.")
        st.caption(outliers.get("caveat", ""))
    else:
        st.caption(outliers.get("reason", "Not enough observations."))

st.write(f"**{chart_spec.label}**")
if chart_spec.valid:
    try:
        st.altair_chart(chart_spec.chart, width="stretch")
    except Exception as exc:
        st.error(f"Could not render the interactive chart: {_safe_error(exc)}")
        try:
            st.image(render_png(plot_type, chart_frame, chart_config),
                     caption="Local PNG fallback", width="stretch")
        except Exception as fallback_exc:
            st.info(f"PNG fallback also failed: {_safe_error(fallback_exc)}")
else:
    st.info(chart_spec.reason)
for warning in chart_spec.warnings:
    st.warning(warning)
for note in chart_spec.notes:
    st.caption(f"• {note}")

with st.expander("Model suggestions (shape heuristics only)"):
    st.dataframe(pd.DataFrame(suggestions), width="stretch", hide_index=True)
    st.caption(
        "Suggestions rank linearised correlations; they are not model selection, "
        "not proof of a mechanism, and not evidence of causation."
    )


# ---------------------------------------------------------------------------
# E · Fit
# ---------------------------------------------------------------------------

step_header("E", "Fit", "The model is fitted only when you choose one; failures are reported instead of hidden.")

is_sample = source_name == SAMPLE.name and model_name == "linear"
slope_label = "Slope (ΔV / ΔI)" if is_sample else f"Slope (Δ{unit_y or 'Y'} / Δ{unit_x or 'X'})"
r2_value = (fit.metrics or {}).get("r2")
f1, f2, f3 = st.columns(3)
f1.metric("Valid measurements", str(fit.n_observations))
f2.metric(slope_label, f"{fit.parameters.get('slope', float('nan')):.5f}"
          if fit.success and "slope" in fit.parameters else "—")
f3.metric("R²", f"{r2_value:.6f}" if isinstance(r2_value, (int, float)) else "Undefined")

if not fit.success:
    st.error(f"Fit failed: {fit.reason}")
else:
    st.code(fit.equation, language="text")
    st.caption(fit.assumptions)
    param_table = pd.DataFrame([
        {"parameter": name, "value": value,
         "std_error": (fit.parameter_errors or {}).get(name)}
        for name, value in fit.parameters.items()
    ])
    left, right = st.columns(2)
    with left:
        st.write("**Parameters**")
        st.dataframe(param_table, width="stretch", hide_index=True)
    with right:
        st.write("**Fit metrics**")
        st.dataframe(pd.DataFrame([
            {"metric": key, "value": value}
            for key, value in (fit.metrics or {}).items()
        ]), width="stretch", hide_index=True)
    for warning in fit.warnings:
        st.warning(warning)
    if fit.x_range:
        st.caption(f"Fitted X range: {fit.x_range[0]:.6g} … {fit.x_range[1]:.6g}. "
                   "Predictions outside it are extrapolations.")
    if uncertainty_values is None:
        st.caption("Unweighted fit (ordinary least squares). No uncertainty column was applied, "
                   "so parameter errors come from residual scatter and are not calibrated.")

with st.expander("Compare candidate models"):
    st.dataframe(pd.DataFrame(model_table), width="stretch", hide_index=True)
    st.caption("AIC comparisons are valid only for fits on the same observations and the same weighting.")

st.write("**Follow-up predictions**")
values = [item.strip() for item in str(candidate_text or "").split(",") if item.strip() != ""]
if not values:
    st.info("Enter at least one candidate value above to see a model-based prediction.")
elif len(values) > MAX_CANDIDATE_VALUES:
    st.info(f"Only the first {MAX_CANDIDATE_VALUES} candidate values are used.")
    values = values[:MAX_CANDIDATE_VALUES]

if values:
    parsed: list[float] = []
    bad_token = False
    parse_failed = False
    for token in values:
        try:
            number = float(token)
        except (TypeError, ValueError):
            parse_failed = True
            break
        if not np.isfinite(number):
            st.error("NaN and infinity are not allowed in candidate values.")
            bad_token = True
            break
        parsed.append(number)
    if parse_failed:
        st.error("Enter finite numeric values separated by commas.")
    if not bad_token and not parse_failed and fit.success:
        prediction = predict_with_flags(fit, np.asarray(parsed, dtype=float))
        if prediction.get("valid"):
            rows = [
                {"candidate_x": x, "predicted_y": y, "range_flag": flag}
                for x, y, flag in zip(prediction["x"], prediction["predicted"],
                                      prediction["range_flags"], strict=True)
            ]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            if all(flag == "in_range" for flag in prediction["range_flags"]):
                st.info("All proposed points are within the measured range; no extrapolation was used.")
            else:
                st.warning("Some proposed points are extrapolated beyond the fitted X range.")
            st.caption(prediction["caveat"])
        else:
            st.info(prediction.get("reason", "Prediction unavailable."))


# ---------------------------------------------------------------------------
# F · Interpret (optional AI)
# ---------------------------------------------------------------------------

step_header("F", "Interpret", "Live Muse Spark is optional. Computed results above are authoritative; "
            "AI text and the explicitly labelled offline MOCK are never experimental evidence.")
st.caption(
    "A live request sends a bounded summary including the question, file and column names, "
    "selected units, cleaning decisions, statistics, fit and warnings. Raw CSV rows are not "
    "intentionally sent, but names and free text may contain sensitive information; review "
    "them before requesting AI. No provider request occurs on startup."
)
st.caption(f"Provider status: {provider['message']} "
           f"(live_verified={str(provider['live_verified']).lower()}, "
           f"mock_available={str(provider['offline_mock_available']).lower()}).")


def _ai_state():
    """Return the current analysis' report state, creating an empty one."""
    state = st.session_state.get("ai_state")
    if isinstance(state, dict) and state.get("hash") == context_hash:
        state.setdefault("live", None)
        state.setdefault("mock", None)
        state.setdefault("active", None)
        return state
    return {"hash": context_hash, "live": None, "mock": None, "active": None}


def _save_ai_state(state):
    state["hash"] = context_hash
    st.session_state["ai_state"] = state


def _set_active_report(kind):
    state = _ai_state()
    state["active"] = kind if kind in ("live", "mock") else None
    _save_ai_state(state)
    wrapper = state.get(state["active"]) if state["active"] else None
    result["ai"] = wrapper
    return wrapper


def _current_report(kind=None):
    """Return a report only when its provenance matches the requested action.

    ``kind=None`` means the currently active report. A live action must not
    reuse a mock, and a mock action must not reuse a live response.
    """
    state = _ai_state()
    if kind is None:
        kind = state.get("active")
        if kind not in ("live", "mock"):
            return None
    if kind not in ("live", "mock"):
        return None
    wrapper = state.get(kind)
    if not isinstance(wrapper, dict) or ask_muse.report_kind(wrapper) != kind:
        return None
    return wrapper


def _active_report():
    state = _ai_state()
    kind = state.get("active")
    if kind not in ("live", "mock"):
        result["ai"] = None
        return None, None
    wrapper = _current_report(kind)
    if wrapper is None:
        state["active"] = None
        _save_ai_state(state)
        result["ai"] = None
        return None, None
    result["ai"] = wrapper
    return kind, wrapper


def _live_request_failed(exc):
    """Safe, actionable failure path; never substitute a mock for live AI."""
    message = _safe_error(exc)
    st.session_state["ai_last_error"] = message
    # Keep a stored mock for a later explicit mock click, but do not display it
    # after a failed live request. Nothing is presented as a live response.
    _set_active_report(None)
    st.error(f"Muse Spark request failed: {message}")
    st.info(
        "No live report was produced. Check BASETEN_API_KEY, model access, "
        "network connectivity and provider quota, then retry. Deterministic "
        "results and exports are unaffected. The labelled OFFLINE MOCK is a "
        "separate action and was NOT substituted for this failed request."
    )


def _mock_request_failed(exc):
    st.session_state["ai_last_error"] = _safe_error(exc)
    st.error(f"Offline mock report could not be generated: {_safe_error(exc)}")


def store_validated_report(wrapper, titles, *, kind):
    """Validate and store a report with explicit, action-appropriate provenance."""
    try:
        wrapper = ask_muse.enforce_report_provenance(wrapper, kind)
    except (ValueError, RuntimeError) as exc:
        if kind == "live":
            _live_request_failed(exc)
        else:
            _mock_request_failed(exc)
        return
    structured = ask_muse.validate_report(
        wrapper.get("structured"), titles, profile=report_profile,
        allowed_evidence_ids=context.get("result_ids"),
    )
    if structured is None:
        st.session_state["ai_last_error"] = "invalid report"
        if kind == "live":
            _set_active_report(None)
        st.error("Report rejected: incomplete report or strict schema validation "
                 "failure; nothing was stored.")
        return
    wrapper["structured"] = structured
    wrapper["analysis_fingerprint"] = context_hash
    wrapper["validation_status"] = "validated"
    from datetime import datetime, timezone
    wrapper["validated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = _ai_state()
    state[kind] = wrapper
    state["active"] = kind
    _save_ai_state(state)
    st.session_state.pop("ai_last_error", None)
    result["ai"] = wrapper
    st.rerun()


regenerate_live = st.checkbox(
    "Regenerate live report on next click", value=False,
    help="Explicitly request a new provider call even if a validated report exists. May consume credits.",
)
if st.button("Generate evidence-grounded interpretation", type="primary"):
    # Reuse ONLY a live report for the same context. A mock never blocks a
    # provider request. The in-flight flag prevents duplicate rapid clicks.
    if _current_report("live") and not regenerate_live:
        _set_active_report("live")
        st.info("A validated live Muse Spark report for this exact analysis is "
                "already available; no duplicate provider request was sent.")
    elif not provider_config.get_api_key():
        if _current_report("mock"):
            st.warning("BASETEN_API_KEY is not set; a labelled OFFLINE MOCK is "
                       "available, but live Muse Spark requires a key. The MOCK "
                       "is NOT a live response. Deterministic results and exports "
                       "remain available.")
        else:
            st.warning("BASETEN_API_KEY is not set; AI interpretation is unavailable. "
                       "All deterministic results and exports remain available. "
                       "Use the labelled offline MOCK button below for a deterministic preview.")
    elif st.session_state.get("ai_request_in_flight"):
        st.info("An AI request is already in progress for this session. "
                "Wait for it to finish before retrying.")
    else:
        st.session_state["ai_request_in_flight"] = True
        st.session_state.pop("ai_last_error", None)
        try:
            with st.spinner("Requesting Muse Spark report..."):
                titles = list(effective_titles)
                if report_profile == ask_muse.DEFAULT_REPORT_PROFILE:
                    wrapper = ask_muse.generate_interpretation(context, section_titles=titles)
                else:
                    wrapper = ask_muse.generate_interpretation(
                        context, section_titles=titles, profile=report_profile
                    )
                wrapper = ask_muse.enforce_report_provenance(wrapper, "live")
        except (ValueError, RuntimeError) as exc:
            _live_request_failed(exc)
        except Exception as exc:
            _live_request_failed(exc)
        else:
            store_validated_report(wrapper, titles, kind="live")
        finally:
            st.session_state.pop("ai_request_in_flight", None)

if st.button("Preview deterministic OFFLINE MOCK report (no API key, NOT AI)",
             key="offline_mock_report"):
    # The mock action reuses ONLY a mock; it never constructs a provider client.
    if _current_report("mock"):
        _set_active_report("mock")
        st.info("A labelled OFFLINE MOCK for this exact analysis is already "
                "available; no duplicate mock was generated.")
    else:
        try:
            wrapper = ask_muse.generate_mock_report(
                context, section_titles=list(effective_titles),
                profile=report_profile, research_question=question,
            )
            wrapper = ask_muse.enforce_report_provenance(wrapper, "mock")
        except (ValueError, RuntimeError) as exc:
            _mock_request_failed(exc)
        except Exception as exc:
            _mock_request_failed(exc)
        else:
            store_validated_report(wrapper, list(effective_titles), kind="mock")

active_kind, current_report = _active_report()
if active_kind == "mock":
    ai_status = "offline MOCK generated (NOT AI)"
elif active_kind == "live":
    ai_status = "succeeded (live AI report, unverified hypotheses)"
elif st.session_state.get("ai_request_in_flight"):
    ai_status = "running"
elif st.session_state.get("ai_last_error"):
    ai_status = "failed"
else:
    ai_status = "not run"
st.caption(f"AI status: {ai_status}. Active provenance: {active_kind or 'none'}. "
           "Live calls require the explicit button above; the agent has a "
           "separate consent checkbox. Local results survive AI failure.")

if current_report:
    wrapper = current_report
    if active_kind == "mock":
        st.markdown("### OFFLINE MOCK report (deterministic template — NOT Muse Spark, NOT AI)")
        st.warning(wrapper.get("disclaimer") or ask_muse.MOCK_DISCLAIMER)
        st.caption(f"Generator: {wrapper.get('model')}. Provider status: "
                   f"{wrapper.get('provider_status')}. No provider request was made.")
    else:
        st.markdown("### Muse Spark report (AI-generated, unverified)")
        st.caption(f"Provider provenance: {wrapper.get('source')} "
                   f"(is_mock={str(wrapper.get('is_mock')).lower()}); "
                   f"provider status: {wrapper.get('provider_status')}; "
                   f"model: {wrapper.get('model')}. Treat this text as hypotheses, not evidence.")
    for section in wrapper["structured"]["sections"]:
        st.markdown(f"**{section['title']}**")
        st.text(section["content"])
    if wrapper["structured"].get("claims"):
        st.markdown("**Evidence-linked claims**")
        for index, claim in enumerate(wrapper["structured"]["claims"], start=1):
            st.text(f"Claim {index} ({claim['evidence_type']}): {claim['claim']}")
            ids = claim.get("evidence_ids") or []
            id_text = f" · Computed result IDs: {', '.join(ids)}" if ids else ""
            st.caption(f"Evidence: {claim['evidence']} · Limitation: {claim['limitation']} · "
                       f"Verification: {claim['proposed_verification']}{id_text}")
    st.info("This report was built from the deterministic context only. "
            "Verify every quantitative statement against sections D and E. "
            "Never present the offline MOCK as a live AI response.")
else:
    st.caption("No report has been generated. The app works fully without an API key; "
               "the offline MOCK is always labelled as a mock.")


# ---------------------------------------------------------------------------
# H · Bounded analysis agent (opt-in, validated tool calls only)
# ---------------------------------------------------------------------------

st.subheader("Optional bounded analysis agent (audit artifacts feed into step G)")
st.caption("Plan -> strict validation -> allowlisted tool execution -> diagnostics -> bounded retry -> grounded interpretation. "
           "This section runs before the export so its audit trail is included in the ZIP.")

agent_audit_files: dict[str, bytes] = {}
agent_consent = st.checkbox(
    "Run the bounded analysis agent (consent: may call Muse Spark when a key is configured)",
    value=False, key="agent_run_consent",
)
agent_use_ai = st.checkbox(
    "Let Muse Spark propose the plan and the final interpretation", value=False,
    key="agent_use_ai",
)
agent_destructive = st.checkbox(
    "Allow destructive agent tools (off by default; no default plan uses them)",
    value=False, key="agent_destructive_consent",
)

if agent_consent:
    with st.spinner("Running bounded agent workflow..."):
        try:
            agent_run = AnalysisOrchestrator(OrchestratorConfig(
                use_ai=bool(agent_use_ai and provider_config.get_api_key()),
                user_confirmed=agent_destructive,
                research_question=question,
            )).run(load)
        except Exception as exc:
            st.error(f"The agent could not complete: {_safe_error(exc)}")
            agent_run = None
    if agent_run is not None:
        agent_data = agent_run.to_dict()
        agent_audit_files = {
            "agent/agent_audit.json": agent_run.to_json_bytes(),
            "agent/agent_events.jsonl": agent_run.to_jsonl(),
            "agent/agent_report.md": agent_run.to_markdown().encode("utf-8"),
        }
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Agent state", agent_data["final"]["state"])
        a2.metric("Plan source", agent_data["plan_source"].replace("_", " "))
        a3.metric("Tool steps", str(agent_data["totals"]["steps"]))
        a4.metric("Retries", str(agent_data["totals"]["retries"]))
        st.caption(f"Research question ({agent_data['question_source']}): "
                   f"{agent_data['research_question']}")
        st.caption(
            "AI decisions = planning/selection. DETERMINISTIC TOOL rows are computed results "
            "from validated Python functions. No model-generated code is executed."
        )
        clarification = agent_data["final"].get("clarification")
        if clarification:
            st.warning("The agent needs clarification before running any tool. "
                       + " ".join(clarification.get("reasons") or []))
            for option in clarification.get("options") or []:
                st.caption(f"• {option}")
        event_rows = [
            {
                "#": event["seq"], "Phase": event["phase"],
                "Actor": "AI DECISION" if event["actor"] == "ai" else "DETERMINISTIC",
                "Tool": event["tool"] or "-", "Status": event["status"],
                "Decision": event["decision"][:160],
            }
            for event in agent_data["events"]
        ]
        st.dataframe(pd.DataFrame(event_rows), width="stretch", hide_index=True)
        with st.expander("Plan validation and data-quality summary"):
            st.json({"plan_validation": agent_data["plan_validation"],
                     "quality_summary": agent_data["quality_summary"]})
        with st.expander("Agent timeline (Mermaid)"):
            st.code(agent_run.mermaid(), language="mermaid")
        st.info(agent_data["final"]["conclusion"])
        if agent_data["final"].get("ai_report", {}):
            report = agent_data["final"]["ai_report"]
            if report.get("rejected"):
                st.warning("An AI report was rejected by the grounding check; the deterministic conclusion was kept.")
            else:
                st.caption("Optional AI sections (unverified hypotheses) are included in agent_report.md.")
        st.caption("Audit artifacts are included in the full export bundle below.")
else:
    st.caption("Agent not run. The standard A-G analysis above is complete and works without any AI service.")


# ---------------------------------------------------------------------------
# G · Export
# ---------------------------------------------------------------------------

step_header("G", "Export", "Every artifact is derived from the single result schema for the current configuration.")

try:
    exports = export_bundle(
        result, cleaned_frame=working, descriptive_table=stats_table,
        charts={**chart_files, **agent_audit_files},
    )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in exports.items():
            archive.writestr(safe_archive_name(name), payload)
    zip_payload = zip_buffer.getvalue()
except Exception as exc:
    st.error(f"Could not build exports: {_safe_error(exc)}")
    st.stop()

d1, d2, d3 = st.columns(3)
d1.download_button("Download cleaned data (CSV)", exports["cleaned_data.csv"],
                   file_name="cleaned_data.csv", mime="text/csv", width="stretch")
d2.download_button("Download results (JSON)", exports["results.json"],
                   file_name="results.json", mime="application/json", width="stretch")
d3.download_button("Download full bundle (ZIP)", zip_payload,
                   file_name="lablens_bundle.zip", mime="application/zip", width="stretch")

st.caption(
    "The ZIP contains: " + ", ".join(sorted(exports)) + ". "
    "The Markdown report includes computed results, limitations, and (only if generated) "
    "clearly labelled AI hypotheses or an explicitly labelled OFFLINE MOCK report."
)
with st.expander("Preview Markdown report"):
    try:
        st.code(markdown_report(result)[:12_000], language="markdown")
    except Exception as exc:
        st.error(f"Could not render the report preview: {_safe_error(exc)}")

st.divider()
st.caption(
    "Built with Muse Spark Open (optional AI). Deterministic analysis is entirely local. "
    "LabLens supports delimited text/CSV analysis only — not universal file formats or all "
    "scientific analyses. Always verify assumptions, units and provenance before drawing conclusions."
)
