
# LabLens AI

**From raw experiment to reproducible scientific insight.**

LabLens AI is a Streamlit research prototype for analyzing paired experimental
measurements. It combines deterministic data cleaning and ordinary least-squares
regression with visual diagnostics, hypothetical follow-up predictions, optional
AI-assisted interpretation, and downloadable records.

## Features

- CSV upload and measurement-column selection
- Duplicate column names rejected with a clear message
- Numeric cleaning with excluded-row counts and source-row tracking
- Linear regression: V = mI + b
- Slope, intercept, R-squared, and RMSE
- Observed-versus-fitted plot and residual plot
- Data-quality warnings (too few points, constant voltage, non-varying current)
- Hypothetical measurement explorer with extrapolation flags
- Optional Muse Spark interpretation through Baseten
- Schema-validated AI reports and evidence-linked claims
- Markdown, CSV, and JSON exports
- Reproducibility record: source filename, SHA-256 fingerprint, row counts,
  cleaning policy, model, metrics, software versions, AI usage flag
- Automated tests for core calculations and provider error handling

## Setup on Windows

Open a VS Code terminal:

```powershell
cd F:\meta-hacathon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If environment activation is blocked, use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run tests

```powershell
python -m pytest -v
```

Baseline result: 26 passed, 1 skipped (the skip is the optional live Muse
Spark test, which requires `BASETEN_API_KEY`).

## Launch the app

```powershell
python -m streamlit run app.py
```

Streamlit will display the local URL, usually http://localhost:8501.

## Optional Muse Spark setup

1. Copy `.env.example` to `.env`.
2. Add your private key as `BASETEN_API_KEY=...`.
3. Restart Streamlit.
4. Click the AI interpretation button when you want to request a report.

The app works without an API key: calculations, plots, and exports remain
available; only AI interpretation is disabled.

Never commit `.env` or expose your API key in source code or screenshots.

## Documentation

- `PROJECT_AUDIT.md` — audit findings, fixes, and unresolved issues
- `docs/ARCHITECTURE.md` — data flow and design
- `docs/SCIENTIFIC_VALIDATION.md` — math definitions and limits
- `docs/DEMO_SCRIPT.md` — 2–3 minute demo sequence
- `docs/HACKATHON_PITCH.md` — pitch summary
- `docs/EVALUATION_PLAN.md` — test and evaluation plan

## Scientific limitations

- A linear fit does not establish that the physical model is correct.
- The slope represents resistance only when the units and experiment justify it.
- Instrument uncertainty, calibration, and systematic errors are not estimated.
- AI-generated interpretations can be wrong and require human review.
- Proposed values are model predictions, not observations.
- Dataset provenance is not independently verified.
- No confidence intervals, parameter standard errors, or outlier removal are provided.

## Demo sequence

1. Load the sample CSV (or upload your own).
2. Show column mapping, units, and data-quality checks.
3. Explain fit metrics, fit plot, and residual plot.
4. Compare predictions inside and outside the measured range.
5. Download the Markdown report and JSON record.
6. Demonstrate AI interpretation if the API is configured.
