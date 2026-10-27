# LabLens AI

**From a raw delimited dataset to a reproducible, assumption-aware analysis.**

LabLens AI is a Streamlit research prototype for general scientific data
analysis. It imports arbitrary CSV/TSV-style tables, lets you choose the X, Y,
group, time, uncertainty and secondary-Y columns yourself, previews cleaning
decisions, computes descriptive statistics and diagnostics, fits a model *you*
select, renders a range of charts, optionally asks **Muse Spark Open** for an
interpretation grounded in the computed results, and exports one coherent
result record.

The original voltage-current sample workflow is preserved unchanged in
`app.py` / `analyze_experiment.py`. The general platform lives in
`general_app.py` / `analyze_dataset.py` and shares the same provider adapter.

> Built with Muse Spark Open. Muse Spark is optional; every number in the app is
> computed locally and works without an API key.

## Which entry point should I use?

| Goal | Command |
| --- | --- |
| General analysis of **any** delimited numeric dataset (steps A-G) | `python -m streamlit run general_app.py` |
| Original voltage-current sample workflow (fully preserved, all legacy tests) | `python -m streamlit run app.py` |
| General headless CLI | `python analyze_dataset.py <file.csv> --x COL --y COL --output-dir outputs/run1` |
| Original headless CLI | `python analyze_experiment.py` |

Both Streamlit scripts are independent, runnable apps. `general_app.py` offers
the bundled voltage-current sample as one of several example datasets; it does
not hardcode those column names or units.

## General platform features (steps A-G)

- **A - Upload.** Bytes/path/file-like inputs; BOM, UTF-8 and cp1252/latin-1
  fallback; `, ; tab |` delimiter sniffing; duplicate raw-header detection;
  explicit rejection of rows wider than the header; 5 MiB / 200,000-row bounds;
  SHA-256 provenance; raw preview.
- **B - Validate / Clean.** Per-column inference (continuous, integer,
  datetime, categorical, boolean, text identifier, empty) shown with reasons;
  missing vs invalid vs non-finite values counted separately; preview before
  consent; optional exact-duplicate removal; invalid values are **never**
  coerced to zero and invalid rows remain in the cleaned CSV; numeric companion
  columns are added instead of overwriting raw values.
- **C - Configure.** User overrides for X, Y, group, time, uncertainty and
  secondary Y; units; scientific question; model, polynomial degree, domain
  layer, correlation method, chart type, bins, AI report sections and optional
  candidate X values for prediction.
- **D - Explore.** Mean/median/percentiles, sample and population variance,
  Student-t CI for the mean, IQR outlier *flags* (never removal), Pearson or
  Spearman correlation with p-value and caveats, sample covariance, correlation
  heatmap. Ten chart types: scatter, line, histogram, box, correlation heatmap,
  time series, grouped comparison, residuals, distribution/density, error bars.
  Charts warn about unsorted lines, dual axes, means without error bars,
  heuristic bins and small groups.
- **E - Fit.** Linear (centred weighted least squares), polynomial (1-6),
  exponential `A*exp(k*x)+C`, logarithmic `A*ln(x)+C`, and power `A*x^k`.
  Weighted fitting uses `w = 1/sigma^2` **only** when a user-supplied
  uncertainty column is finite and positive. Convergence failures, domain
  violations and underdetermined fits are returned as explicit reasons, not
  tracebacks. Model suggestions are labelled shape heuristics; AIC /
  adjusted-R² comparison is shown. Predictions flag extrapolation.
- **F - Interpret.** Optional Muse Spark report generated only from a compact,
  deterministic-only context (no raw rows, no prior AI text). Eight legacy
  sections remain the default; a registry of ten sections allows opt-in
  alternatives. Strict validation rejects unexpected/duplicate/oversized
  sections, extra keys, and empty content. AI prose is labelled as unverified
  hypotheses.
- **G - Export.** One result schema (v2.0) drives cleaned CSV, descriptive
  statistics CSV, fit parameter and metric CSVs, strict JSON, Markdown report,
  interactive plot HTML and locally rendered plot PNG, all bundled in a ZIP.

### Domain layers are explicit, never inferred

`generic` (default) reports no physical constants. `ohmic`, `calibration` and
`growth` are opt-in and list their assumptions. An Ohmic resistance in ohms is
computed **only** when the user selects that layer *and* supplies a consistent
current/voltage unit pair. Filenames and column names never select a domain.

## Quick start

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run general_app.py
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run general_app.py
```

If activation is blocked, call `.venv\Scripts\python.exe` directly. No
compiler or system package is required: SciPy, Altair, pandas and Streamlit
all ship wheels for CPython 3.11/3.12 on Linux and Windows.
`requirements.lock.txt` records the exact verified environment (Linux,
CPython 3.11.2). For development/CI tooling:

```bash
python -m pip install -r requirements-dev.txt
```

### CLI examples

```bash
# Original sample with explicit columns and an Ohmic domain layer
python analyze_dataset.py data/sample_voltage_current.csv \
  --x current_A --y voltage_V --unit-x A --unit-y V --domain ohmic \
  --output-dir outputs/sample

# Weighted calibration on a different dataset, with columns inferred
python analyze_dataset.py data/examples/synthetic_calibration.csv \
  --uncertainty abs_sigma --domain calibration --output-dir outputs/cal

# Columns inferred automatically; curved model
python analyze_dataset.py data/examples/synthetic_quadratic.csv \
  --model polynomial --degree 2 --output-dir outputs/quad
```

Synthetic example datasets are documented in `data/examples/README.md`. They
are computer-generated, **not** experimental evidence.

## Quality gates

```bash
python -m pytest -q                 # offline suite (live provider tests skip)
python -m pytest -m live -v         # opt-in, billable live provider tests
ruff check .
python -m compileall -q *.py
```

Measured in this repository on 27 Oct 2026 (Linux, CPython 3.11,
pandas 3.1.0, numpy 2.4.6, SciPy 1.17.1, Altair 6.3.0, Streamlit 1.66.1):

- **229 passed, 2 skipped** (the skips are the opt-in live Muse Spark tests);
  117 new tests were added to the original 112.
- `ruff check .` clean; `python -m compileall -q *.py` exits 0.
- **91% statement coverage** of the nine new deterministic modules plus the
  general CLI (1,338 of 1,463 statements; per module 87-98%).
- Streamlit `AppTest` runs both UI scripts, including different-column uploads,
  role changes, cleaning previews, invalid inputs, AI validation and exports.
- Local Streamlit HTTP smoke test: `/` and `/_stcore/health` returned 200 for
  `general_app.py` on `0.0.0.0:8503`.
- GitHub Actions CI on PR #2: all 4 matrix jobs passed (Ubuntu/Windows x
  Python 3.11/3.12).
- See `docs/IMPLEMENTATION_REPORT.md` for the exact commands, per-phase status,
  acceptance assessment and open items.

Offline fake-client tests verify **our side** of the provider contract. No
`BASETEN_API_KEY` was configured here, so the live Baseten integration remains
**unverified**; `docs/PROVIDER_INTEGRATION.md` describes the contract.

## Optional Muse Spark setup

1. Copy `.env.example` to `.env` (never commit `.env`).
2. Add your private key as `BASETEN_API_KEY=...`.
3. Restart Streamlit.

The app works without a key: calculations, plots and exports remain available;
only AI interpretation is disabled. The default model is the officially
documented `meta-models/muse-spark-open`. If your account was assigned a dated
variant, set `BASETEN_MODEL` in `.env`. Never commit, print or screen-share a
key; provider errors are redacted.

## Supported scope and honest limitations

**Supported:** delimited text files (`.csv`, `.tsv`, `.txt`) with a header row,
dot decimal separator, and numeric columns that can be parsed as floats.
Encoding fallback covers UTF-8/BOM, cp1252 and latin-1. Delimiters `,`, `;`,
tab and `|` are sniffed.

**Not supported:** Excel/XLSX, JSON, HDF5, Parquet, binary instrument formats,
images, locale-specific decimal commas, multi-header/multi-index sheets,
quoted fields containing embedded newlines in a row wider than the header,
automatic unit conversion, automatic scientific-domain detection, causal
inference, survival/time-to-event analysis, multivariate regression, mixed
effects, or any claim of "all scientific analyses".

Other limitations:

- CSV parsing caps rows at 200,000 and plots at 50,000 rows; aggregate or
  filter larger data before upload.
- Interactive HTML plots load Vega-Lite from jsDelivr and need internet to
  render. PNG plots are rendered locally with Matplotlib.
- Confidence intervals are sampling intervals under stated assumptions, not
  instrument accuracy. Parameter errors in unweighted fits derive from
  residual scatter and are not calibrated.
- No measurement uncertainties are invented; error bars and weighted fitting
  require an explicit, finite, positive uncertainty column. A supplied column
  is assumed to be 1-sigma; the app cannot tell SD from SEM for you.
- Correlation and fitted coefficients do not establish causation.
- Outliers are flagged, never removed. Duplicate removal is opt-in.
- Extrapolated predictions are model-based projections, not measurements.
- AI text can be wrong; verify every quantitative claim against sections D/E.
- Dataset provenance is user supplied and not independently verified.

## Documentation

- `docs/GENERAL_PLATFORM.md` - module map, result schema, design decisions
- `docs/IMPLEMENTATION_REPORT.md` - measured results, changes and open items
- `PROJECT_AUDIT.md` - historical audit of the original sample workflow
- `docs/ARCHITECTURE.md` - original data flow
- `docs/SCIENTIFIC_VALIDATION.md` - equations and numerical tests
- `docs/PROVIDER_INTEGRATION.md` - Muse Spark contract and verification status
- `docs/EVALUATION_PLAN.md`, `docs/DEMO_SCRIPT.md`, `docs/HACKATHON_*.md` - evaluation and submission material
- `data/examples/README.md` - synthetic datasets
- `results/README.md` - CLI output artifacts

## Hackathon context

Verified from the official event page and Official Rules (26 Oct 2026):
submissions due **4 Nov 2026, 9:00 PM ET** via the Cerebral Valley portal;
judging weights Impact 30%, Use of Meta AI Tooling 25%, Technical Depth &
Execution 20%, Demo 25%. The rules text we read did not state demo-video length
or repository-visibility requirements; confirm in the participant portal. See
`docs/HACKATHON_RULES.md`.
