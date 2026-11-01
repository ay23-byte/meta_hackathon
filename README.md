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

### Quick synthetic demo (no API key or upload)

Run `python -m streamlit run general_app.py`, then choose
`linear_calibration_demo.csv` in the bundled examples. Select `time_s` and
`signal_mV` as X and Y and a linear model. The deliberately messy synthetic
file has 15 rows, including three invalid responses; the 12 valid pairs fit
slope 2.5 and intercept 0.1. This is a software demonstration, not experimental
evidence. See [the demo script](docs/DEMO_SCRIPT.md) for a judge-facing
walkthrough and the honest offline AI fallback. JSON and Markdown reports
record a small allowlist of runtime versions; this is useful provenance, not a
complete environment lock or a guarantee of reproducibility.

### Evidence and reproducibility (offline)

The general dashboard includes an inspectable deterministic evidence ledger
for its insight cards. IDs are bound to the current core analysis and point to
local result paths; they do not validate interpretation or prove causality.
The JSON and Markdown reports contain the ledger, and the ZIP/CLI bundle includes
`manifest.json` with source and artifact checksums and selected settings. The
manifest is not signed and does not capture a complete environment. Review
exports for sensitive names and units before sharing.

Optional AI responses undergo strict schema/evidence-ID checks and a limited
numerical check for explicit slope, intercept, R², RMSE and n statements.
Contradictory statements are rejected; unchecked numbers, units, citations,
semantic support and interpretations remain unverified. Offline mock output is
clearly labelled and is not a live provider response. Full details and gaps:
[roadmap](docs/ROADMAP.md).

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
  heatmap. Eleven chart types: scatter, line, histogram, box, correlation heatmap,
  time series, grouped comparison, residuals against X or fitted values,
  distribution/density, error bars.
  Charts warn about unsorted lines, dual axes, means without error bars,
  heuristic bins and small groups.
- **E - Fit.** Linear (centred weighted least squares), polynomial (1-6),
  exponential `A*exp(k*x)+C`, logarithmic `A*ln(x)+C`, and power `A*x^k`.
  Weighted fitting uses `w = 1/sigma^2` **only** when a user-supplied
  uncertainty column is finite and positive. Convergence failures, domain
  violations and underdetermined fits are returned as explicit reasons, not
  tracebacks. Model suggestions are labelled shape heuristics; AIC /
  adjusted-R² comparison is shown. Predictions flag extrapolation; conditional
  95% mean-response and individual prediction intervals are available for
  unweighted linear fits with sufficient data. Weighting requires an explicit
  uncertainty-column selection.
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

## Conditional fit uncertainty

Successful unweighted linear fits with positive residual degrees of freedom
have conditional 95% slope/intercept Student-t intervals, with assumptions
and limitations. Weighted/nonlinear intervals and measurement accuracy are
not inferred. An optional calculator propagates user-supplied independent
standard uncertainties for four arithmetic operations. See
[uncertainty scope](docs/MATHEMATICS_AND_UNCERTAINTY.md).

## Offline experiment comparison

The general app can compare two explicitly mapped datasets after confirmation
of matching units and experimental compatibility. The comparison is descriptive,
not a test of causation or statistical significance. See
[comparison workflow and limits](docs/EXPERIMENT_COMPARISON.md).

## Key insights

After configuration, deterministic cards highlight supported fit, data-quality
and diagnostic findings with result-field evidence and limitations. Their fixed
ordering is not a confidence score. Verify units, including header-based hints,
before interpretation. See [insight rules and limitations](docs/INSIGHT_ENGINE.md).

## Conditional theory chapter

The optional research panel includes an offline Ohmic teaching chapter after
explicit user confirmation, with a unit-aware fit interpretation and an
illustrative (not measured) example. See [theory scope and limitations](docs/SCIENTIFIC_THEORY_ENGINE.md)
and [upgrade progress](docs/IMPLEMENTATION_PROGRESS.md).

## Offline research notes

The optional research context provides explicitly user-confirmed Ohmic theory
notes, reliability cautions, and model-comparison curves without a provider.
See [docs/RESEARCH_ASSISTANT.md](docs/RESEARCH_ASSISTANT.md) for scope and
limitations, including features not yet implemented.

## Current readiness

See [docs/HACKATHON_READINESS.md](docs/HACKATHON_READINESS.md) for the latest
local audit, offline demo checklist and explicit live-provider and security
limitations. A configured key does not establish a successful live request.

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

Measured in this repository on 28 Oct 2026 (Linux, CPython 3.11,
pandas 3.1.0, numpy 2.4.6, SciPy 1.17.1, Altair 6.3.0, Streamlit 1.66.1):

- **426 passed, 2 skipped** (the skips are the opt-in live Muse Spark tests);
  the hardening and provenance phases added 78 regression tests on top of the
  348-test master-prompt baseline.
- `ruff check .` clean; `python -m compileall -q *.py` exits 0.
- Final coverage run: **92% (2,130/2,305 statements)** across
  `provider_config`, `ask_muse`, `result_schema`, `data_io`, fitting/statistics
  core and the agent modules. Earlier phases measured 91% / 90% on smaller
  module sets; those are historical, not the final number.
  Seven-case agent demo passes `--strict` with all observed states matching
  expectations (A, B, B', C, C', D, E).
- Streamlit `AppTest` runs both UI scripts, including different-column uploads,
  role changes, cleaning previews, invalid inputs, AI validation and exports.
- Local Streamlit HTTP smoke test: `/` and `/_stcore/health` returned 200 for
  `general_app.py` on `0.0.0.0:8503`.
- GitHub Actions CI on PR #5: all 4 matrix jobs passed on this branch
  (Ubuntu/Windows x Python 3.11/3.12), verified with `gh pr checks 5 --watch`.
  Earlier PR #2 and PR #3 also passed all 4 matrix jobs on each;
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

### Additional opt-in analysis and PDF export

The general app offers a two-input correlated uncertainty calculator and seeded
bivariate-normal Monte Carlo quantiles, conditional Welch intervals for independent
experiment means, and a user-supplied Ohmic resistance comparison. Each requires
explicit assumptions; the outputs do not establish causation or validate a physical
model. Monte Carlo quantiles are not confidence intervals, and the Welch interval
does not account for paired measurements or different X distributions.

Select **Include text-first PDF report in ZIP** to add an optional PDF; generated PNG plots are embedded
as figure pages and also remain separate artifacts. The general CLI also accepts `--pdf`. Oversized PDFs
are refused rather than silently truncated. PDF layout, accessibility and broad
Unicode coverage have not been comprehensively verified. See
[`docs/ROADMAP.md`](docs/ROADMAP.md) for feature status and limitations.

For a longer offline submission rehearsal, see the extended synthetic Ohmic
walkthrough in [`docs/LIVE_DEMO_GUIDE.md`](docs/LIVE_DEMO_GUIDE.md). The two
constructed datasets are not real measurements or independent replications.
The optional comparison fits separate unweighted straight lines and reports
descriptive differences; it does not establish statistical significance.

## Optional local Meta Llama 3.2 1B (Ollama)

The general dashboard supports **Meta Llama 3.2 1B and 3B — Local Ollama** separately
from the optional Muse Spark/Baseten provider and the deterministic offline
mock. Python computes all results. On the same machine running Streamlit, start
Ollama and install your chosen model yourself; LabLens never downloads a model.

```powershell
# Install Ollama separately from its official distribution first.
ollama serve                    # only if the Ollama service is not already running
ollama pull llama3.2:3b         # explicit one-time model download by the user
python -m streamlit run general_app.py
```

In **Meta Llama 3.2 — Local Ollama (optional)**, enable controls, select 1B or 3B,
press **Check local Ollama and model**, then **Generate local Llama report**. You can
add a question about the current analysis before generating. The application
sends a compact summary to `127.0.0.1:11434` on the **server machine**, not the
user's browser. If Streamlit is hosted remotely, it cannot reach the Ollama
process on your personal Windows machine without a separate, deliberately
configured secure architecture; this app does not expose or proxy Ollama.
Never expose Ollama publicly for a demo.

Responses must pass the existing report schema, evidence-ID checks, and a
limited numerical contradiction guard. AI meaning, unsupported numbers, units,
citations and scientific conclusions remain unverified; a small model may fail
JSON/schema validation. A failed request never becomes a mock or a remote call.
The five optional experiment templates are educational guidance only: they do
not choose variables, infer a physical experiment, or perform new domain-specific
calculations. See `docs/DEMO_GUIDE.md` and `docs/SCIENTIFIC_METHOD.md`.

### Optional user-configured hosted model

A separate hosted adapter can be enabled only with explicitly configured process
variables, user consent, and a button press. It defaults to the requested
`meta-models/Muse-Glimmer-30B` identifier but **does not include or verify an
endpoint, model entitlement, free credits, or pricing**. No real hosted request
has been verified here. See [hosted setup and safety](docs/HOSTED_MODEL_SETUP.md)
before configuring it. Do not share credentials or sensitive experiment context.

### Bluesminds Muse Glimmer 30B (optional)

Install the project and launch the general app (Python 3.11 or 3.12 recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Obtain a Bluesminds API key from your provider account. Never share it or put it
in source control. Set the following in the **same PowerShell process** before
starting Streamlit; this adapter reads process environment only, not `.env`:

```powershell
$env:LABLENS_AI_PROVIDER = "bluesminds"
$key = Read-Host "Bluesminds API key" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($key)
try { $env:BLUESMINDS_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); Remove-Variable key, ptr }
.\.venv\Scripts\python.exe -m streamlit run general_app.py
```

Default endpoint is `https://api.bluesminds.com/v1` and requested model is
`meta/muse-glimmer-30b`. Optionally override them with `LABLENS_BASE_URL`
(HTTPS only) and `LABLENS_MODEL`. Set `LABLENS_MAX_OUTPUT_TOKENS` (128–8192,
default 512) or `LABLENS_TIMEOUT_SECONDS` (5–120, default 60) if needed. The
request uses temperature 0.2, top_p 1, and `reasoning_effort=none`. Existing
Muse Spark and generic hosted modes remain separate. Restart Streamlit after
changing environment variables.

With `LABLENS_AI_PROVIDER=bluesminds`, **F · Interpret** explicitly selects
Bluesminds rather than Muse Spark. Review the data-sharing and billing warning,
check the F consent box, then click **Generate evidence-grounded interpretation**.
The sidebar separately shows key detection, model configuration, session
connectivity verification and validated generation; none proves billing or model
identity. Changes to analysis or provider settings invalidate the F consent and
cached live report. An unset provider retains the legacy Muse Spark workflow.
An unsupported provider value fails closed rather than switching providers.

Alternatively, in **Hosted model (explicit configuration and consent)**, enable
controls, review the warning, and give consent. The optional
**Test hosted API connectivity** button sends one potentially billable short
completion; report generation sends analysis context. Neither happens on a
rerun automatically. No automatic retries or provider fallback are made.

Troubleshooting: a missing-key message means the variable was not set in the
Streamlit process or contains a placeholder. HTTP 401 means authentication was
rejected; 402 indicates payment/quota; 429 indicates rate limiting or quota;
5xx indicates a provider error. An HTTP 402 from F while Muse Spark is selected
is a Baseten response, not evidence about Bluesminds credits. Confirm the
selected provider in the sidebar. Timeouts may require retrying manually after
checking service status. Empty or truncated output and invalid reports are
rejected, not replaced with reasoning or a mock; increasing the token limit
may help truncation but can increase cost. With no API or a failed request,
Python calculations and exports remain available and AI interpretation is
unavailable. Report validation checks schema and evidence IDs and applies a
limited numeric guard; it cannot prove scientific claims, all numbers, units
or semantic support. Review interpretations independently. No live endpoint,
model access, credits, pricing, or identity have been verified by these tests.
See [hosted setup](docs/HOSTED_MODEL_SETUP.md).
