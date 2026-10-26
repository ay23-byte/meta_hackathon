# LabLens AI demo script (2–3 minutes)

A truthful, executable demo using the bundled sample dataset. Never present
a mock or saved AI report as a live Muse Spark result. If the API is
unavailable, use the fallback path below and say so out loud.

## Setup

Open the dashboard on the bundled sample (`python -m streamlit run app.py`).
Do not show or speak your `BASETEN_API_KEY`. Confirm the sidebar shows the
AI provider status (configured or not configured).

---

### 0:00–0:20 — The problem

Open the dashboard on the bundled sample. Say:

> "Lab data analysis often jumps from spreadsheet to conclusion without an
> auditable path. LabLens keeps the calculation deterministic, makes the
> cleaning explicit, and makes AI interpretation optional and evidence-grounded."

Show the hero header and the scientific safeguards in the sidebar.

### 0:20–0:45 — Upload and map data

Show the source preview of `data/sample_voltage_current.csv` (11 rows), the
detected current/voltage column selections, the units (A and V), and the
research question. Point out the provenance note ("not independently
verified") and that column mapping is manual when automatic detection is
uncertain.

### 0:45–1:10 — Deterministic fit and diagnostics

Show slope, intercept, R², and RMSE in the metric cards. Say the numbers come
from the tested Python analysis core, not from AI. Show the fit plot and the
residual plot. Emphasize:

- R² does not prove the physical model.
- Invalid paired rows are counted and excluded, never silently dropped.
- No outliers are removed automatically.

### 1:10–1:35 — Hypothetical follow-up (explorer)

Show the measurement explorer table. Compare one candidate inside the
measured range with one outside it. State that predictions are model
outputs, hypothetical, and that out-of-range predictions are extrapolations
unsupported by the measured data.

### 1:35–2:00 — AI interpretation (only if configured)

If `BASETEN_API_KEY` is configured and network access is available, press
"Generate evidence-grounded interpretation". Explain:

- Muse Spark receives only a compact result summary (question, columns and
  units, row counts, fit metrics, residual summary, limitations) — never the
  raw CSV and never the API key.
- The report is validated against a strict schema before it is shown.
- Every AI claim is labeled as not independently verified and must be checked
  against the numerical record.

Show the eight sections and the evidence-linked claims table.

### 2:00–2:20 — Export reproducibility

Download the Markdown report, cleaned CSV, and JSON analysis record. Point to:
source filename, SHA-256 input fingerprint, original and retained row counts,
model equation, metrics, software versions, and the AI-used flag.

### 2:20–2:40 — Close

Restate the value: reproducible calculations first, optional evidence-grounded
AI second, with uncertainty and limitations shown explicitly.

---

## Fallback path (API unavailable or not configured)

Skip step 5. Show the local numerical dashboard, plots, and downloads instead.
Say out loud: "Muse Spark is optional. Missing credentials or provider access
does not affect calculation, plots, or exports." Never show a mock or saved
report as a live API result, and never expose the API key.
