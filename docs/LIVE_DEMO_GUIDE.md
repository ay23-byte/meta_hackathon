# LabLens AI — reproducible 2–3 minute live demo

This guide uses only functionality verified in this repository. The dataset is
synthetic; see `data/demo/README.md`. No real API key is needed for the core
demo. If you use live Muse Spark, configure the key locally and never show it.

## 1. Setup (Windows PowerShell)

Run from your local repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Optional environment configuration — copy the example, then edit `.env`
locally. **Never commit, print or screen-share `.env`.**

```powershell
Copy-Item .env.example .env
notepad .env
```

Put your own private value in `.env` as `BASETEN_API_KEY=...`. The repository
only contains the placeholder in `.env.example`. A key being present does not
prove live reachability; the sidebar configuration check always shows `live_verified=false`; a validated live report is shown separately after a successful request. `LABLENS_DISABLE_DOTENV=1` can be set in CI/tests to ignore
`.env`; do not set it for a live demo.

## 2. Launch

```powershell
.\.venv\Scripts\python.exe -m streamlit run general_app.py
```

Legacy app (optional comparison):

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 3. Exact demo sequence (about 2:45)

| Time | Action | Expected observable output |
| --- | --- | --- |
| 0:00–0:20 | Open the app. Show the "First time here?" expander and sidebar "Provider status". | Workflow A–G is visible. State is either "key not configured" or "key configured, live NOT verified". |
| 0:20–0:45 | Step A: upload `data/demo/linear_calibration_demo.csv`. | 15 source rows, 4 columns, UTF-8, SHA-256 provenance. State clearly: "This is synthetic data, not an experiment." |
| 0:45–1:10 | Step B: review validation/cleaning. | `signal_mV` shows 1 missing, 1 invalid, 1 non-finite; 3 rows excluded from fitting but retained in cleaned CSV. No value becomes zero. |
| 1:10–1:35 | Step C: set X=`time_s`, Y=`signal_mV`, model=`linear`; set Scientific question to "How does signal_mV vary with time_s?". | User-controlled roles and units; no domain is inferred from the filename. |
| 1:35–2:00 | Steps D–E: show scatter/residual plots and fit metrics. | Slope `2.5`, intercept `0.1`, R² `1.0`, 12 observations. Say these are computed locally, not AI. |
| 2:00–2:20 | Step F: press **Preview deterministic OFFLINE MOCK report (no API key, NOT AI)**. Read the disclaimer aloud. | Heading "OFFLINE MOCK report — NOT Muse Spark, NOT AI"; scientific sections quote only the computed numbers. If a working key is configured, press the separate live button instead and label the text "AI-generated, unverified". |
| 2:20–2:35 | Step G: download cleaned CSV, JSON and ZIP. | Three download buttons; ZIP contains `results.json`, `report.md`, fit CSVs, statistics CSV, cleaned CSV and plots. |
| 2:35–2:45 | In a terminal, show the offline verification. | `.\.venv\Scripts\python.exe -m pytest -q` → report the actual local pass/skip counts; live provider tests are opt-in. |

PowerShell CLI equivalent for the same synthetic dataset (writes a labelled
offline mock report without any network call):

```powershell
.\.venv\Scripts\python.exe -B analyze_dataset.py data\demo\linear_calibration_demo.csv --x time_s --y signal_mV --model linear --output-dir outputs\demo --ai-mock --report-profile scientific --question "How does signal_mV vary with time_s?"
```

Expected CLI lines:

```text
Source: linear_calibration_demo.csv (15 rows)
Fit successful: True  n = 12
Equation: signal_mV = 2.5 * time_s + 0.1
R2: 1.0
OFFLINE MOCK report written (deterministic template, NOT Muse Spark, NOT AI).
```

## 4. Optional live Muse Spark check (explicit opt-in only)

Live tests are never part of the ordinary suite. They require both a real key
and `--run-live`:

```powershell
.\.venv\Scripts\python.exe -m pytest --run-live -m live -v
```

If the provider is unreachable, those tests skip with a clear environment
message. Do not claim live integration from a skipped test. To exercise the UI
live path, press **Generate evidence-grounded interpretation** once; the app
guards against duplicate requests from reruns. A provider failure shows an
actionable error and keeps all local results and downloads.

## 5. Troubleshooting

- **"BASETEN_API_KEY is not set"**: expected offline. Add a local `.env` or
  use the labelled OFFLINE MOCK button. Never paste a key into chat.
- **Key is an obvious placeholder**: replace `your_baseten_api_key_here` in
  `.env`; the app treats it as not configured.
- **403 / model access**: the app now distinguishes credential, permission,
  model-access and quota hints from the provider response when available.
- **Provider unreachable / timeout**: deterministic analysis, plots, exports,
  agent audit and offline mock remain available.
- **App reruns after a widget change**: local computations are cached; the
  bounded agent runs only when its consent checkbox is selected. Live AI calls
  require the explicit button and are not repeated for an unchanged context.
- **Unsupported file**: use `.csv`, `.tsv` or `.txt` with a header row and dot
  decimal separator. Excel/JSON/Parquet/binary formats are out of scope.


### Note on mock then live

If you demonstrate the OFFLINE MOCK first, pressing **Generate
evidence-grounded interpretation** afterwards now performs a real provider
request when a key is configured. The mock is not reused as a live response;
it remains available under its own labelled action. A provider failure shows
an error and does not silently substitute the mock.

## Extended offline synthetic Ohmic walkthrough

For a longer technical rehearsal, upload `data/demo/synthetic_ohmic_a.csv`.
Explicitly map X `current_A` with unit `A`, Y `voltage_V` with unit `V`, and
choose a linear model. The data are **synthetic**, not real measurements.
Show the fit, residuals and conditional parameter intervals; explain their
assumptions. Under **Compare with a proposed Ohmic prediction**, enable the
comparison, enter 10 ohm and confirm the physical mapping and assumed value.
The difference from `V=10 I` is descriptive, not proof or a hypothesis test.

In **Compare a second experiment**, upload `synthetic_ohmic_b.csv`, map the
same columns and units, and explicitly confirm compatibility. These constructed
files are not independent replications. Select **Fit separate unweighted lines**
for descriptive fit differences, and optionally the conditional Welch interval
only after reading its independence assumptions. Inspect the evidence panel,
preview the explicitly labelled OFFLINE MOCK, and enable text-first PDF in the
ZIP export. Generated PNG plots appear on PDF figure pages and remain separate
files; interactive HTML plots remain separate. The generated
Markdown and manifest are example reports; use a fresh scratch directory and
avoid private data. This extended walkthrough is tested with Streamlit AppTest,
not a recorded judge-facing video or a live model demonstration.

Run the tests in your own environment and report the actual result.
