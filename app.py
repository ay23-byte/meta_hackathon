
"""LabLens AI: scientific analysis dashboard."""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import ask_muse
import provider_config
from analysis_core import (
    analyze_linear,
    detect_candidate_columns,
    prepare_analysis_data,
    propose_measurements,
    serialize_analysis_exports,
)

ROOT = Path(__file__).resolve().parent

# Bounds on untrusted input. These protect both the UI and the AI context.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024       # 5 MiB of CSV
MAX_SOURCE_ROWS = 200_000
MAX_CANDIDATE_VALUES = 50
MAX_SHORT_TEXT = 300
MAX_UNIT_TEXT = 24
MAX_CANDIDATE_TEXT = 2000

st.set_page_config(
    page_title="LabLens AI",
    page_icon="🔬",
    layout="wide",
)


def safe_unit(value, fallback):
    """Return a unit string that is safe in labels and CSV column headers.

    CSV consumers such as Excel interpret cells beginning with ``= + - @``
    as formulas, so unit text must never be allowed to inject one.
    """
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_./^\-°µΩ ]", "", text)[:MAX_UNIT_TEXT]
    text = text.strip()
    if not text:
        return fallback
    if text[0] in "=+-@":
        text = "'" + text
    return text


def md_inline(value):
    """Make untrusted text safe to place on one line of the Markdown report."""
    text = " ".join(str(value).split())
    text = text.replace("\\", "\\\\").replace("`", "'").replace("|", "\\|")
    return text[:MAX_SHORT_TEXT]


def json_safe(value):
    """Convert NumPy values and non-finite numbers to JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def validated_ai_structure(report):
    """Return the sanitized report body, or ``None`` when it is invalid."""
    from ask_muse import validate_report

    if not isinstance(report, dict) or not isinstance(report.get("model"), str):
        return None
    return validate_report(report.get("structured"))


def validate_ai_report(report):
    """Check the AI report wrapper against the single authoritative schema.

    Delegates to ``ask_muse.validate_report`` rather than maintaining a
    second copy of the rules. This guarantees the UI can never render or
    export a report the producer would have rejected (8 required titles,
    each exactly once, all six claim fields, and all size limits).
    """
    return validated_ai_structure(report) is not None


def read_csv_safely(file_object, filename, max_bytes=MAX_UPLOAD_BYTES):
    """Read CSV data with an explicit size bound and useful parse errors."""
    try:
        size = getattr(file_object, "size", None)
        if size is None and isinstance(file_object, (str, Path)):
            size = Path(file_object).stat().st_size
        if size is not None and size > max_bytes:
            st.error(
                f"{filename} is {size:,} bytes, which exceeds the "
                f"{max_bytes:,}-byte limit. Upload a smaller CSV."
            )
            st.stop()
        return pd.read_csv(file_object)
    except (
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        UnicodeDecodeError,
        ValueError,
        OSError,
    ) as exc:
        st.error(f"Could not read {filename}: {type(exc).__name__}: {exc}")
        st.stop()


def make_context_hash(record, explorer_records):
    """Bind an AI report to the complete displayed analysis context."""
    from ask_muse import MODEL

    payload = {
        "source_hash": record["input_sha256"],
        "question": record["scientific_question"],
        "columns": record["selected_columns"],
        "units": record["units"],
        "results": record["results"],
        "row_counts": record["row_counts"],
        "explorer": explorer_records,
        "provider_model": MODEL,
    }
    encoded = json.dumps(
        payload, sort_keys=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_analysis_record(
    source, source_hash, current_col, voltage_col,
    current_unit, voltage_unit, question, description,
    prepared, analysis,
):
    """Create a reproducible numerical-analysis record."""
    return json_safe({
        "application": "LabLens AI",
        "application_version": "1.1.0",
        "software_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": plt.matplotlib.__version__,
            "streamlit": st.__version__,
        },
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "source_file": source,
        "input_sha256": source_hash,
        "data_provenance": (
            "Unknown unless described by the user; not independently verified."
        ),
        "scientific_question": question,
        "dataset_description": description or None,
        "selected_columns": {
            "current": current_col,
            "voltage": voltage_col,
        },
        "units": {
            "current": current_unit,
            "voltage": voltage_unit,
        },
        "row_counts": {
            "original": prepared["original_rows"],
            "retained": prepared["valid_rows"],
            "dropped": prepared["dropped_rows"],
        },
        "cleaning_policy": (
            "Selected columns are converted to numeric. Rows with missing, "
            "nonnumeric, NaN, or infinite selected values are excluded. "
            "Source row order is preserved; no automatic outlier removal."
        ),
        "model": {
            "name": "Ordinary least squares",
            "equation": "V = mI + b",
            "rmse_convention": "sqrt(mean(residual**2)); denominator n",
        },
        "results": {
            "slope": analysis["slope"],
            "intercept": analysis["intercept"],
            "r_squared": analysis["r_squared"],
            "rmse": analysis["rmse"],
            "n": analysis["n"],
            "mean_current": float(np.mean(prepared["current"])),
            "mean_voltage": float(np.mean(prepared["voltage"])),
        },
        "warnings": [
            "High R-squared does not establish physical correctness.",
            "Instrument uncertainty and calibration are not included.",
            "Model assumptions and units must be scientifically appropriate.",
        ],
        "ai_interpretation_generated": False,
        "ai_provider_model": None,
    })


# ---------------------------------------------------------
# Professional dashboard styling
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1450px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(128,128,128,.22);
    }
    .hero {
        padding: 1.6rem 1.8rem;
        border: 1px solid rgba(100,160,210,.35);
        border-radius: 18px;
        background: linear-gradient(
            125deg, rgba(24,71,105,.25), rgba(67,51,105,.16)
        );
        margin-bottom: 1.3rem;
    }
    .eyebrow {
        text-transform: uppercase;
        letter-spacing: .14em;
        font-size: .76rem;
        font-weight: 700;
        opacity: .75;
    }
    .hero h1 {
        margin: .45rem 0;
        font-size: clamp(2rem,4vw,3.2rem);
        letter-spacing: -.04em;
    }
    .hero p {
        font-size: 1.05rem;
        max-width: 800px;
        opacity: .88;
    }
    div[data-testid="stMetric"] {
        padding: 1rem;
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 14px;
        background: rgba(128,128,128,.045);
    }
    div[data-testid="stDownloadButton"] button {
        width: 100%;
        border-radius: 10px;
        min-height: 2.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">AI-assisted scientific discovery</div>
      <h1>🔬 LabLens AI</h1>
      <p>From raw experiment to verified scientific insight — transparent
      numerical analysis, visual diagnostics, and optional AI interpretation.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Experiment setup")
    st.caption(
        "Numerical analysis runs locally. AI is called only when requested."
    )
    st.markdown(
        """
        **Scientific safeguards**
        - AI does not modify measured data.
        - Invalid paired rows are counted and excluded.
        - Proposed measurements are hypothetical.
        - Fit metrics do not prove physical validity.
        - Provenance is not independently verified.
        """)

    st.divider()
    st.subheader("AI provider status")
    _api_key_configured = provider_config.api_key_status()["present"]
    if _api_key_configured:
        st.success("Muse Spark via Baseten is configured.")
    else:
        st.info(
            "Muse Spark via Baseten is not configured. Add "
            "BASETEN_API_KEY to a local .env file to enable AI "
            "interpretation. Calculations and exports remain available."
        )
    from ask_muse import MODEL

    st.caption(
        f"Model: {MODEL} · Endpoint: "
        "https://inference.baseten.co/v1 · Raw data and API key are "
        "never sent as context."
    )
    st.caption("Built with Muse Spark Open.")

    st.divider()
    st.subheader("Workflow")
    st.caption(
        "1 · Inspect data\n"
        "2 · Map columns and units\n"
        "3 · Run deterministic fit\n"
        "4 · Review plots and residuals\n"
        "5 · Optional AI interpretation\n"
        "6 · Export reproducible record"
    )

# ---------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------

uploaded = st.file_uploader(
    "Upload experiment data (CSV)",
    type=["csv"],
)

if uploaded is None:
    sample_path = ROOT / "data" / "sample_voltage_current.csv"

    if not sample_path.is_file():
        st.info("Upload a CSV to begin; the bundled sample was not found.")
        st.stop()

    st.info(
        "Using the bundled demonstration dataset. Its provenance has not "
        "been independently verified."
    )
    raw_bytes = sample_path.read_bytes()
    source = sample_path.name
    raw = read_csv_safely(sample_path, source)
else:
    raw_bytes = uploaded.getvalue()
    source = Path(uploaded.name).name[:120]
    raw = read_csv_safely(uploaded, source)

if raw.empty or len(raw.columns) == 0:
    st.error("The CSV contains no usable rows or columns.")
    st.stop()

if len(raw) > MAX_SOURCE_ROWS:
    st.error(
        f"The CSV has {len(raw):,} rows, which exceeds the "
        f"{MAX_SOURCE_ROWS:,}-row limit. Upload a smaller dataset."
    )
    st.stop()

# ---------------------------------------------------------
# 2. Inspect and configure
# ---------------------------------------------------------

st.subheader("1 · Inspect and configure")
st.caption(f"{source} · {len(raw):,} source rows · {len(raw.columns)} columns")
st.dataframe(raw.head(8), width="stretch", hide_index=True)

description = st.text_input(
    "Dataset description or provenance (optional)",
    max_chars=MAX_SHORT_TEXT,
)
columns = list(raw.columns)
guess_i = detect_candidate_columns(columns, "current")
guess_v = detect_candidate_columns(columns, "voltage")

c1, c2, c3, c4 = st.columns(4)

with c1:
    current_col = st.selectbox(
        "Current column",
        columns,
        index=columns.index(guess_i) if guess_i in columns else 0,
    )
with c2:
    voltage_index = (
        columns.index(guess_v)
        if guess_v in columns
        else min(1, len(columns) - 1)
    )
    voltage_col = st.selectbox(
        "Voltage column", columns, index=voltage_index
    )
with c3:
    current_unit = st.text_input(
        "Current unit", value="A", max_chars=MAX_UNIT_TEXT
    )
with c4:
    voltage_unit = st.text_input(
        "Voltage unit", value="V", max_chars=MAX_UNIT_TEXT
    )

question = st.text_input(
    "Scientific question",
    value="How does voltage vary with current over the measured range?",
    max_chars=MAX_SHORT_TEXT,
)

# Sanitize unit strings before they reach plot labels, CSV headers and the
# exported record. See safe_unit() for the CSV-formula-injection rationale.
current_unit = safe_unit(current_unit, "A")
voltage_unit = safe_unit(voltage_unit, "V")

if current_col == voltage_col:
    st.error("Choose different columns for current and voltage.")
    st.stop()

try:
    prepared = prepare_analysis_data(raw, current_col, voltage_col)
except (ValueError, TypeError, KeyError) as exc:
    st.error(f"Cannot prepare selected columns: {exc}")
    st.stop()

if prepared["valid_rows"] < 2:
    st.error("At least two valid paired measurements are required.")
    st.stop()

x = np.asarray(prepared["current"], dtype=float)
y = np.asarray(prepared["voltage"], dtype=float)

try:
    analysis = analyze_linear(x, y)
except (ValueError, TypeError, np.linalg.LinAlgError) as exc:
    st.error(f"The selected measurements cannot support a fit: {exc}")
    st.stop()

fitted = np.asarray(analysis["fitted"], dtype=float)
residuals = np.asarray(analysis["residuals"], dtype=float)

if (
    fitted.size != x.size
    or residuals.size != x.size
    or not np.all(np.isfinite(fitted))
    or not np.all(np.isfinite(residuals))
):
    st.error("Regression output contains invalid fitted values or residuals.")
    st.stop()

clean = prepared["data"].copy()
clean["fitted_voltage"] = fitted
clean["residual_voltage"] = residuals
clean = clean.rename(
    columns={
        "current_A": f"current_{current_unit.strip() or 'unitless'}",
        "voltage_V": f"voltage_{voltage_unit.strip() or 'unitless'}",
    },
)

st.success(
    f"Retained {prepared['valid_rows']} of {prepared['original_rows']} rows; "
    f"excluded {prepared['dropped_rows']} invalid paired row(s)."
)
if prepared["dropped_rows"]:
    st.caption(
        "Invalid selected measurements were excluded. No automatic outlier "
        "removal was performed."
    )
if prepared["valid_rows"] == 2:
    st.warning(
        "Only two measurements remain. A line can be fitted, but there are "
        "no residual degrees of freedom to assess fit quality."
    )

# ---------------------------------------------------------
# 3. Data quality
# ---------------------------------------------------------

st.subheader("2 · Data quality and model readiness")

distinct_i = int(np.unique(x).size)
distinct_v = int(np.unique(y).size)
warnings = []

if distinct_i < 3:
    warnings.append(
        "Fewer than three distinct current values are available; the "
        "relationship is difficult to assess."
    )
if distinct_v < 2:
    warnings.append(
        "Voltage has no observed variation. R-squared is undefined."
    )
if prepared["valid_rows"] < 5:
    warnings.append(
        "Few valid measurements remain. Treat fit statistics cautiously."
    )

q1, q2, q3 = st.columns(3)
q1.metric("Valid measurements", prepared["valid_rows"])
q2.metric("Distinct current values", distinct_i)
q3.metric("Distinct voltage values", distinct_v)

for warning in warnings:
    st.warning(warning)

if not warnings:
    st.success(
        "Basic checks passed. This does not prove physical validity."
    )

# ---------------------------------------------------------
# 4. Numerical analysis
# ---------------------------------------------------------

st.subheader("3 · Deterministic analysis")
cu = current_unit.strip() or "unit"
vu = voltage_unit.strip() or "unit"

m1, m2, m3, m4 = st.columns(4)
m1.metric("Slope (ΔV / ΔI)", f"{analysis['slope']:.6g} {vu}/{cu}")
m2.metric("Intercept", f"{analysis['intercept']:.6g} {vu}")
m3.metric(
    "R²",
    "Undefined" if analysis["r_squared"] is None
    else f"{analysis['r_squared']:.6f}",
)
m4.metric("Voltage RMSE", f"{analysis['rmse']:.5g} {vu}")

st.latex(r"V = mI + b")
st.caption(
    f"V = {analysis['slope']:.7g} × I + ({analysis['intercept']:.7g}). "  # noqa: RUF001 - intentional multiplication sign
    "RMSE uses denominator n. The slope represents resistance only when "
    "the units and physical model justify that interpretation."
)

# ---------------------------------------------------------
# 5. Visual diagnostics
# ---------------------------------------------------------

st.subheader("4 · Visual diagnostics")
left, right = st.columns(2)

with left:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(x, y, label="Observed measurements", color="#137c8b", zorder=3)
    order = np.argsort(x)
    ax.plot(x[order], fitted[order], label="OLS fitted model", color="#e07a3f")
    ax.set_xlabel(f"Current ({cu})")
    ax.set_ylabel(f"Voltage ({vu})")
    ax.set_title("Measurements and fitted line")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

with right:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axhline(0, color="#555555", linewidth=1)
    ax.scatter(x, residuals, color="#7047a3")
    ax.set_xlabel(f"Current ({cu})")
    ax.set_ylabel(f"Residual ({vu})")
    ax.set_title("Residuals against current")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

st.caption(
    "Residual plots may reveal patterns but do not independently establish "
    "independence, normality, or constant variance."
)

with st.expander("Model assumptions and limitations"):
    st.markdown(
        """
        This dashboard fits an unweighted ordinary least-squares line and
        treats the selected x and y values as exact. Instrument calibration,
        measurement uncertainty, repeatability, and systematic effects are
        not estimated. No outliers are automatically removed.
        """
    )

with st.expander("Retained data, fitted values, and residuals"):
    st.dataframe(clean, width="stretch", hide_index=True)

# ---------------------------------------------------------
# 6. Hypothetical measurement explorer
# ---------------------------------------------------------

st.subheader("5 · Explore a follow-up measurement")
st.write(
    "Predictions are calculated from the fitted model. They are not "
    "observed experimental measurements."
)

low, high = float(np.min(x)), float(np.max(x))
step = (high - low) / 10 if high > low else 1.0

candidate_text = st.text_input(
    "Candidate current values (comma-separated)",
    value=f"{low:.6g}, {(low + high)/2:.6g}, {high:.6g}, {high + step:.6g}",
    max_chars=MAX_CANDIDATE_TEXT,
)

explorer = pd.DataFrame()
try:
    candidates = [
        float(item.strip())
        for item in candidate_text.split(",")
        if item.strip()
    ]
    if not candidates:
        raise ValueError("Enter at least one candidate.")
    if len(candidates) > MAX_CANDIDATE_VALUES:
        candidates = candidates[:MAX_CANDIDATE_VALUES]
        st.info(
            f"Only the first {MAX_CANDIDATE_VALUES} candidate values are used."
        )
    if not np.all(np.isfinite(candidates)):
        raise ValueError("NaN and infinity are not allowed.")

    explorer = propose_measurements(candidates, analysis, x)
    st.dataframe(explorer, width="stretch", hide_index=True)

    outside = int((~explorer["within_observed_range"].astype(bool)).sum())
    if outside:
        st.warning(
            f"{outside} candidate(s) are outside the measured range "
            f"[{low:g}, {high:g}]. Their predictions are extrapolations."
        )
    else:
        st.info(
            "All proposed points are within the measured range. This does "
            "not validate predictions outside that range."
        )
except (ValueError, TypeError, KeyError, OverflowError) as exc:
    st.error(f"Enter finite numeric values separated by commas. {exc}")
    explorer = pd.DataFrame()

# ---------------------------------------------------------
# 7. Reproducible record
# ---------------------------------------------------------

record = create_analysis_record(
    source=source,
    source_hash=hashlib.sha256(raw_bytes).hexdigest(),
    current_col=current_col,
    voltage_col=voltage_col,
    current_unit=current_unit,
    voltage_unit=voltage_unit,
    question=question,
    description=description,
    prepared=prepared,
    analysis=analysis,
)

explorer_records = json_safe(explorer.to_dict(orient="records"))
record["explorer"] = {
    "method": "Linear prediction and observed-range check; no uncertainty interval.",
    "candidates": explorer_records,
}

# ---------------------------------------------------------
# 8. Optional Muse Spark interpretation
# ---------------------------------------------------------

st.subheader("6 · Optional Muse Spark interpretation")
st.caption(
    "When requested, the app sends a compact summary of the experiment to "
    "Baseten. The raw CSV and API key are not intentionally sent as context."
)

current_hash = make_context_hash(record, explorer_records)


def stored_live_report():
    """Return a context-matching live report, never an offline mock.

    Legacy wrappers without provenance are treated as live for backward
    compatibility; an explicitly labelled mock is not reused by the live
    action and is not displayed as a Muse Spark report.
    """
    report = st.session_state.get("lablens_ai_report")
    if st.session_state.get("lablens_ai_context_hash") != current_hash:
        return None
    if not isinstance(report, dict) or report.get("is_mock"):
        return None
    source = report.get("source")
    if source not in (None, ask_muse.LIVE_REPORT_SOURCE):
        return None
    return report


existing_report = stored_live_report()

if st.button("Generate evidence-grounded interpretation", type="primary"):
    # A rerun alone never calls the provider. The in-flight flag and the
    # context-bound existing report both prevent duplicate paid requests.
    if existing_report:
        st.info("A validated report for this exact analysis is already available; "
                "no duplicate provider request was sent.")
    elif not provider_config.get_api_key():
        st.warning(
            "BASETEN_API_KEY is not set. Numerical analysis and downloads "
            "remain available."
        )
    elif st.session_state.get("lablens_ai_request_in_flight"):
        st.info("An AI request is already in progress for this session. "
                "Wait for it to finish before retrying.")
    else:
        st.session_state["lablens_ai_request_in_flight"] = True
        st.session_state.pop("lablens_ai_last_error", None)
        try:
            from ask_muse import generate_interpretation

            context = {
                "scientific_question": question,
                "dataset": {
                    "filename": source,
                    "description": description or None,
                    "provenance": "Not independently verified.",
                    "raw_rows": prepared["original_rows"],
                    "retained_rows": prepared["valid_rows"],
                    "dropped_rows": prepared["dropped_rows"],
                },
                "variables": {
                    "x": {"name": current_col, "unit": current_unit},
                    "y": {"name": voltage_col, "unit": voltage_unit},
                },
                "model": "V = mI + b (ordinary least squares)",
                "results": record["results"],
                "residual_summary": {
                    "mean": float(np.mean(residuals)),
                    "min": float(np.min(residuals)),
                    "max": float(np.max(residuals)),
                },
                "limitations": record["warnings"] + warnings,
                "hypothetical_follow_up_candidates": explorer_records,
            }

            with st.spinner("Requesting interpretation from Muse Spark..."):
                ai_report = generate_interpretation(context)

            if validate_ai_report(ai_report):
                st.session_state["lablens_ai_report"] = ai_report
                st.session_state["lablens_ai_context_hash"] = current_hash
                st.session_state.pop("lablens_ai_last_error", None)
            else:
                st.session_state["lablens_ai_last_error"] = "incomplete report"
                st.error("Muse Spark returned an incomplete report.")

        except Exception as exc:
            st.session_state["lablens_ai_last_error"] = provider_config.redact(str(exc))
            st.error(f"Muse Spark request failed: {provider_config.redact(str(exc))}")
        finally:
            st.session_state.pop("lablens_ai_request_in_flight", None)

ai_report = stored_live_report()
if ai_report:
    ai_status = "succeeded (unverified AI hypotheses)"
elif st.session_state.get("lablens_ai_request_in_flight"):
    ai_status = "running"
elif st.session_state.get("lablens_ai_last_error"):
    ai_status = "failed"
else:
    ai_status = "not run"
st.caption(f"AI status: {ai_status}. Calculations, plots and exports do not depend on AI.")

# Reuse the sanitized structure for rendering AND export so no untrusted
# provider keys can reach the UI or the downloaded record.
ai_structure = validated_ai_structure(ai_report) if ai_report else None

if ai_structure:
    record["ai_interpretation_generated"] = True
    record["ai_provider_model"] = f"Baseten / {ai_report['model']}"
    record["ai_interpretation"] = ai_structure

    st.markdown("### Muse Spark report")
    st.caption(
        "AI statements are not independently verified. Check every claim "
        "against the numerical results and original experiment. Content is "
        "shown as plain text so model output cannot inject links or markup."
    )

    for section in ai_structure["sections"]:
        st.markdown(f"**{section['title']}**")
        st.text(section["content"])

    claims = ai_structure["claims"]
    if claims:
        st.markdown("**Evidence-linked claims**")
        st.dataframe(pd.DataFrame(claims), width="stretch", hide_index=True)

# ---------------------------------------------------------
# 9. Export report, cleaned CSV, and JSON
# ---------------------------------------------------------

st.subheader("7 · Export reproducible record")

warning_text = (
    "\n".join("- " + warning for warning in warnings)
    if warnings else "- No basic data-quality warnings were triggered."
)

report = f"""# LabLens AI scientific analysis

- **Source:** {md_inline(source)}
- **Input SHA-256:** `{record['input_sha256']}`
- **UTC timestamp:** {record['analysis_timestamp_utc']}
- **Question:** {md_inline(question)}
- **Current column:** {md_inline(current_col)} ({md_inline(current_unit)})
- **Voltage column:** {md_inline(voltage_col)} ({md_inline(voltage_unit)})
- **Rows retained:** {prepared['valid_rows']}
- **Original rows:** {prepared['original_rows']}
- **Rows excluded:** {prepared['dropped_rows']}
- **Model:** V = mI + b (ordinary least squares)
- **Slope:** {analysis['slope']:.9g}
- **Intercept:** {analysis['intercept']:.9g}
- **R²:** {analysis['r_squared']}
- **RMSE:** {analysis['rmse']:.9g}

## Data quality

{warning_text}

## Limitations

Data provenance is not independently verified. Fit metrics do not prove
physical validity. Calibration, measurement uncertainty, and systematic
effects are not estimated. No outliers were automatically removed.

Candidate values are hypothetical. Predictions outside the observed range
are extrapolations and are not validated by these data.
"""

if ai_structure:
    report += "\n## Muse Spark interpretation\n\n"
    report += "AI-generated; not independently verified.\n\n"
    report += json.dumps(
        ai_structure,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    )

exports = serialize_analysis_exports(record, clean, report)

e1, e2, e3 = st.columns(3)
e1.download_button(
    "Download report (.md)",
    exports["markdown"],
    "lablens_scientific_report.md",
    "text/markdown",
)
e2.download_button(
    "Download cleaned data (.csv)",
    exports["csv"],
    "cleaned_and_fitted_data.csv",
    "text/csv",
)
e3.download_button(
    "Download analysis record (.json)",
    exports["json"],
    "analysis_results.json",
    "application/json",
)

st.divider()
st.caption(
    "LabLens AI · Deterministic analysis with optional AI interpretation. "
    "Verify provenance, units, assumptions, and experimental conditions "
    "before drawing scientific conclusions."
)
