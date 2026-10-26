# LabLens AI

**From raw experiment to reproducible scientific insight.**

LabLens AI is a Streamlit research prototype for analyzing paired
experimental measurements. It combines deterministic, numerically stable
ordinary least-squares regression with visual diagnostics, hypothetical
follow-up predictions, optional AI-assisted interpretation via **Muse Spark
Open** (Baseten), and downloadable reproducibility records.

> Built with Muse Spark Open.

## Features

- CSV upload (5 MiB / 200,000-row limits) or bundled sample dataset
- Automatic column suggestions with manual confirmation; unit inputs
- Duplicate column names rejected; transparent invalid-row counts and
  source-row tracking
- Numerically stable centred OLS `V = mI + b`: slope, intercept, R², RMSE
- Observed-versus-fitted plot and residual plot
- Data-quality warnings (few points, constant voltage, non-varying current)
- Hypothetical measurement explorer with explicit extrapolation flags
- Optional Muse Spark interpretation with a strict, size-limited, sanitized
  report schema and evidence-linked claims
- AI report bound to the displayed analysis by a SHA-256 context hash
- Markdown, cleaned CSV, and JSON exports with input fingerprint, cleaning
  policy, warnings, software versions, and AI-usage status
- Headless-friendly CLI sharing the same analysis core
- 112 offline tests, 98% statement coverage, lint-clean, Linux + Windows CI

## Quick start

### Windows (PowerShell)

```powershell
cd F:\meta-hacathon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If activation is blocked, use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Run

```bash
python -m streamlit run app.py          # dashboard, usually localhost:8501
python analyze_experiment.py            # CLI artifacts into results/
python analyze_experiment.py --output-dir outputs
```

`requirements.lock.txt` records the exact environment used for verification
(Linux, CPython 3.11.2). For development/CI tooling:

```bash
python -m pip install -r requirements-dev.txt
```

## Quality gates

```bash
python -m pytest -q                    # offline suite
python -m pytest -m "not live" -q --cov=analysis_core --cov=ask_muse --cov=app --cov=analyze_experiment
ruff check .
```

Measured on 26 Oct 2026 in this repository:

- **112 passed, 2 skipped** (skips are the opt-in live provider tests)
- **98% statement coverage** across the four application modules
- `ruff check .` clean; all modules byte-compile
- Streamlit AppTest executes the real UI script, including upload errors
  and the AI report path

Live tests are opt-in and billable:

```bash
python -m pytest -m live -v
```

Offline fake-client tests verify **our side** of the provider contract;
they are not evidence that the live endpoint is reachable. See
`docs/PROVIDER_INTEGRATION.md`.

## Optional Muse Spark setup

1. Copy `.env.example` to `.env`.
2. Add your private key as `BASETEN_API_KEY=...`.
3. Restart Streamlit.

The app works without an API key: calculations, plots, and exports remain
available; only AI interpretation is disabled. The default model is the
officially documented `meta-models/muse-spark-open`. If your hackathon
account is assigned a dated variant, set `BASETEN_MODEL` in `.env` instead
of editing source.

Never commit `.env`, print a key, show it in a recording, or paste it into
an issue. Errors are redacted and no raw provider exception text is shown.

## Scientific limitations

- A linear fit does not establish that the physical model is correct.
- The slope represents resistance only when the units and experiment
  justify that interpretation.
- Instrument uncertainty, calibration, and systematic errors are not
  estimated. No confidence intervals, parameter standard errors, weighting,
  or automatic outlier removal are provided.
- AI-generated interpretations can be wrong and require human review;
  numerical claims must be checked against the deterministic record.
- Proposed values are model predictions, not observations; out-of-range
  predictions are extrapolations.
- Dataset provenance is user supplied and not independently verified.
- R² is undefined (not zero) when voltage has no variance.

## Documentation

- `PROJECT_AUDIT.md` — audit findings, fixes, measured results, open items
- `docs/ARCHITECTURE.md` — data flow and design
- `docs/SCIENTIFIC_VALIDATION.md` — equations, tests, limits
- `docs/PROVIDER_INTEGRATION.md` — Muse Spark contract and verification status
- `docs/EVALUATION_PLAN.md` — measured quality gates and proposed work
- `docs/DEMO_SCRIPT.md` — ~2:45 demo and recording guide
- `docs/HACKATHON_RULES.md` — verified official requirements vs. community claims
- `docs/HACKATHON_CHECKLIST.md` — submission checklist and outstanding items
- `docs/HACKATHON_PITCH.md` — pitch mapped to the four judging criteria
- `results/README.md` — what the CLI writes and why outputs are gitignored

## Hackathon context

Verified from the official event page and Official Rules (26 Oct 2026):
submissions are due **4 Nov 2026, 9:00 PM ET** via the Cerebral Valley
portal; judging weights are Impact 30%, Use of Meta AI Tooling 25%,
Technical Depth & Execution 20%, Demo 25%; two tracks and two themes
("Build for Your World" and "Push the Frontier"). LabLens fits the latter.
Video length and repository-visibility requirements are **not** stated in
the rules text we read — confirm in the participant portal. See
`docs/HACKATHON_RULES.md`.

## Demo sequence

1. Load the sample CSV (or upload your own).
2. Show column mapping, units, and data-quality checks.
3. Explain fit metrics, fit plot, and residual plot.
4. Compare predictions inside and outside the measured range.
5. Download the Markdown report and JSON record.
6. Demonstrate AI interpretation if the API is configured; otherwise show
   the honest fallback path.
