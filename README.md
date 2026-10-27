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

**Master-prompt update (27 Oct 2026).** The report layer now has two strictly
validated profiles (`legacy` eight sections by default and an opt-in
`scientific` eight-section report), computed-result IDs that every AI claim
must cite, bounded retries for transient provider failures, and an honest
`provider_status()` that never claims live verification. A deterministic
**OFFLINE MOCK** report is available from a separate, conspicuously labelled
button and `--ai-mock`; it is never presented as Muse Spark output. The bounded
agent now records a user research question, asks for clarification on vague
questions before running any tool, and has three additional allowlisted tools
(`compare_models`, `evidence_summary`, `time_series_summary`). Reproducible
demos A-E include an ambiguous question and a simulated provider outage.

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
  deterministic-only context (no raw rows, no prior AI text). The `legacy`
  eight-section profile remains the default; a `scientific` profile adds
  Research Question / Dataset Overview / Analysis Performed / Main Quantitative
  Findings / Model-Fit Assessment / Possible Scientific Interpretation /
  Recommended Next Investigation. Every claim must cite computed `result_ids`.
  Strict validation rejects unexpected/duplicate/oversized sections, extra
  keys, bad evidence IDs and empty content. AI prose is labelled as unverified
  hypotheses. A separate button and `--ai-mock` generate an explicitly labelled
  deterministic OFFLINE MOCK report — **NOT AI** — for offline demos.
- **G - Export.** One result schema (v2.0) drives cleaned CSV, descriptive
  statistics CSV, fit parameter and metric CSVs, strict JSON, Markdown report,
  interactive plot HTML and locally rendered plot PNG, all bundled in a ZIP.

### Domain layers are explicit, never inferred

`generic` (default) reports no physical constants. `ohmic`, `calibration` and
`growth` are opt-in and list their assumptions. An Ohmic resistance in ohms is
computed **only** when the user selects that layer *and* supplies a consistent
current/voltage unit pair. Filenames and column names never select a domain.

## Bounded analysis agent (observable autonomy)

LabLens is not just a CSV dashboard with an AI summary. An **Analysis
Orchestrator** (`agent_core.py`) runs a bounded, testable loop:

0. The user research question is recorded; a deterministic gate requests
   clarification with concrete options before **any** tool runs if it is vague.
1. `inspect_dataset` produces a structured data-quality summary.
2. Muse Spark (or an offline fallback) proposes a plan of tool names and
   parameters — **never code**.
3. `validate_plan` rejects unknown tools, bad parameters, forbidden tokens and
   oversized plans before anything executes.
4. A closed registry (`docs/TOOL_REGISTRY.md`) dispatches thirteen validated
   Python tools: statistics, correlation, model comparison, evidence summary,
   time-series summary, plotting, fitting and diagnostics.
5. Deterministic diagnostics inspect the actual fit; poor fits trigger a
   bounded retry with a validated alternative model.
6. The agent may stop with `INSUFFICIENT_EVIDENCE` or `NEEDS_CLARIFICATION`.
7. The final conclusion is assembled from executed tool outputs; optional AI
   sections are rejected if they contain numbers absent from those outputs.
8. Every plan, validation decision, tool call, result, retry and conclusion is
   written to `agent_audit.json`, `agent_events.jsonl` and `agent_report.md`.

Limits: 8 steps, 2 retries, 3 fit attempts, 5 s per tool, 30 s per run,
50,000 rows, 20 columns, polynomial degree <= 4. No `eval`, no shell, no
arbitrary paths, no row deletion or imputation. Destructive tools require an
explicit, default-off UI consent checkbox.

```bash
python run_agent_demo.py --case all --strict --output-dir outputs/agent_demo
python analyze_dataset.py data/agent_examples/case_b_curved.csv --agent --output-dir outputs/agent
```

Seven reproducible cases cover five required scenarios: success (A), poor
initial fit with a validated alternative (B), no justifiable model (B'),
messy-data recovery (C), ambiguous schema (C'), ambiguous research question
(D) and a simulated provider outage (E) that falls back to a deterministic
plan and writes a labelled OFFLINE MOCK report. Everything runs offline; with
`BASETEN_API_KEY` set, `--use-ai` / `--agent-use-ai` let Muse Spark propose the
plan. See `docs/AGENT_WORKFLOW.md` for the diagram, verification matrix and the
explicit list of live-unverified behaviours.

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
python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m streamlit run general_app.py
```

Exact PowerShell verification commands (run from the repository root):

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q -x '\.venv|\.git' .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest --run-live -m live -q
.\.venv\Scripts\python.exe -B run_agent_demo.py --case all --strict --output-dir outputs\agent_demo
.\.venv\Scripts\python.exe -B analyze_dataset.py data\sample_voltage_current.csv --x current_A --y voltage_V --output-dir outputs\sample --ai-mock --report-profile scientific --question "What is the slope?"
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

# Explicitly labelled offline MOCK scientific report (no key, no network)
python analyze_dataset.py data/sample_voltage_current.csv \
  --x current_A --y voltage_V --ai-mock --report-profile scientific \
  --question "What is the slope?" --output-dir outputs/mock
```

Synthetic example datasets are documented in `data/examples/README.md`. They
are computer-generated, **not** experimental evidence.

## Quality gates

```bash
python -m pytest -q                         # offline suite; live tests always skip
python -m pytest --run-live -m live -v      # explicit opt-in, billable live provider tests
ruff check .
python -m compileall -q *.py
```

`provider_config.py` reads `.env` with `dotenv_values` without mutating
`os.environ`; process environment variables always win. Tests set
`LABLENS_DISABLE_DOTENV=1`, so a developer `.env` can never make an ordinary
`pytest` run contact Baseten. Obvious placeholder keys are treated as not
configured. Live tests require both `--run-live` and a usable key.

Measured in this repository on 27 Oct 2026 (Linux, CPython 3.11,
pandas 3.1.0, numpy 2.4.6, SciPy 1.17.1, Altair 6.3.0, Streamlit 1.66.1):

- **419 passed, 2 skipped** (the skips are the opt-in live Muse Spark tests);
  the hardening phase added 71 regression tests on top of the 348-test
  master-prompt baseline.
- `ruff check .` clean; `python -m compileall -q *.py` exits 0.
- Final coverage run: **92% (2,103/2,276 statements)** across
  `provider_config`, `ask_muse`, `result_schema`, `data_io`, fitting/statistics
  core and the agent modules. Earlier phases measured 91% / 90% on smaller
  module sets; those are historical, not the final number.
  Seven-case agent demo passes `--strict` with all observed states matching
  expectations (A, B, B', C, C', D, E).
- Streamlit `AppTest` runs both UI scripts, including different-column uploads,
  role changes, cleaning previews, invalid inputs, AI validation and exports.
- Local Streamlit HTTP smoke test: `/` and `/_stcore/health` returned 200 for
  `general_app.py` on `0.0.0.0:8503`.
- GitHub Actions CI on PR #2 and PR #3: all 4 matrix jobs passed on each
  (Ubuntu/Windows x Python 3.11/3.12). PR #3 initially failed both Windows
  jobs on a ~15 ms `time.monotonic()` resolution assumption in one new test;
  fixed with a platform-independent deadline (`docs/IMPLEMENTATION_REPORT.md`).
- See `docs/IMPLEMENTATION_REPORT.md` for the exact commands, per-phase status,
  acceptance assessment and open items.

Offline fake-client tests verify **our side** of the provider contract, and
orchestrator tests prove that two different *validated* plans produce two
different executed tool sequences. No `BASETEN_API_KEY` was configured here, so
the live Baseten integration — including a real Muse-proposed plan driving a
real run — remains **unverified**. `docs/PROVIDER_INTEGRATION.md` describes the
contract; `docs/AGENT_WORKFLOW.md` lists exactly which agent behaviours are
implemented, verified offline, and still unverified live.

## Optional Muse Spark setup

1. Copy `.env.example` to `.env` (never commit `.env`).
2. Add your private key as `BASETEN_API_KEY=...`.
3. Restart Streamlit.
4. For live integration tests only, run `python -m pytest --run-live -m live -v`.

The app works without a key: calculations, plots, exports, agent audit trails
and the explicitly labelled OFFLINE MOCK report remain available; only *live*
AI interpretation is disabled. The sidebar shows an honest provider status
(`live_verified` is always false until a real call is observed). The default model is the officially
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

- `docs/PROJECT_AUDIT.md` - measured baseline audit and master-prompt resolution log
- `docs/HARDENING_REPORT.md` - root-cause analysis of the six historical failures and Phase B-K verification
- `docs/LIVE_DEMO_GUIDE.md` - exact 2-3 minute demo with PowerShell commands
- `data/demo/README.md` - synthetic demo dataset and expected computed results
- `docs/AGENT_WORKFLOW.md` - agent diagram, bounds, A-E demo cases, verification matrix
- `docs/TOOL_REGISTRY.md` - the closed allowlist and parameter specs
- `docs/GENERAL_PLATFORM.md` - module map, result schema, design decisions
- `docs/IMPLEMENTATION_REPORT.md` - measured results, changes and open items
- `PROJECT_AUDIT.md` - historical audit of the original sample workflow
- `docs/ARCHITECTURE.md` - original data flow plus master-prompt boundaries
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
