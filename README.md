
# LabLens AI

**From raw experiment to reproducible scientific insight.**

LabLens AI is a Streamlit research prototype for analyzing paired experimental
measurements. It combines deterministic data cleaning and ordinary least-squares
regression with visual diagnostics, hypothetical follow-up predictions, optional
AI-assisted interpretation, and downloadable records.

## Features

- CSV upload and measurement-column selection
- Numeric cleaning with excluded-row counts
- Linear regression: V = mI + b
- Slope, intercept, R-squared, and RMSE
- Observed-versus-fitted plot and residual plot
- Basic data-quality warnings
- Hypothetical measurement explorer
- Optional Muse Spark interpretation through Baseten
- Markdown, CSV, and JSON exports
- Input file SHA-256 fingerprint
- Automated tests for core calculations

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

Never commit `.env` or expose your API key in source code or screenshots.

## Scientific limitations

- A linear fit does not establish that the physical model is correct.
- The slope represents resistance only when the units and experiment justify it.
- Instrument uncertainty, calibration, and systematic errors are not estimated.
- AI-generated interpretations can be wrong and require human review.
- Proposed values are model predictions, not observations.
- Dataset provenance is not independently verified.

## Demo sequence

1. Load the sample CSV.
2. Show the selected measurement columns and data-quality checks.
3. Explain the fit metrics and residual plot.
4. Compare predictions inside and outside the measured range.
5. Download the Markdown report and JSON record.
6. Demonstrate AI interpretation if the API is configured.
