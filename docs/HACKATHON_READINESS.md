# LabLens AI — hackathon readiness (28 Oct 2026)

## Decision

**Conditional GO for a synthetic, offline-first demo.** The deterministic
workflow, labelled mock, exports and bounded-agent demos have passed the checks
below. **NO GO for claiming a verified live Muse Spark round trip** until a
real, explicitly initiated request succeeds in the demo environment. These
checks do not constitute scientific certification or a security audit.

## Implemented and verified offline

- Delimited CSV/TSV/text import, validation, explicit cleaning and user-selected
  roles; deterministic summaries, association, fits, charts, exports and
  optional domain layers. `general_app.py` is the general workflow; `app.py`
  and `analyze_experiment.py` preserve the voltage/current workflow.
- Separate live and deterministic offline mock actions, strict report
  validation, context-bound cache and explicit regeneration. Mocked provider
  tests cover failures and provenance; no automatic startup provider call.
- Bounded allowlisted agent, explicit consent and audit trails; seven synthetic
  demo scenarios produced their expected states.
- This audit fixed ascending AIC ordering, rank-deficient polynomial fits,
  undefined constant-column correlation diagonals, unequal/nonfinite covariance,
  CLI mock-as-live rejection, untrusted Markdown rendering and spreadsheet formula
  protection in export cells and headers. Existing tests were retained; the
  constant-correlation assertion was corrected to the mathematically undefined value.

## Verification (Linux, CPython 3.11.2, 28 Oct 2026)

- `.venv/bin/python -m pytest -q`: **436 passed, 2 skipped**; skipped tests are
  live-provider opt-in tests. `.venv/bin/ruff check .`: pass.
- `.venv/bin/python -m compileall -q -x '\.venv|\.git' .`: pass.
- `.venv/bin/python -m pytest --run-live -m live -q`: **2 skipped, 436 deselected**;
  no usable key, no provider request was made.
- `run_agent_demo.py --case all --strict`: **7/7** expected states. README's
  four general CLI examples and legacy CLI completed. Synthetic calibration
  demo recovered slope 2.5 and intercept 0.1 (12 valid observations).
- Opened and checked synthetic output: JSON, four CSVs, Markdown, five PNGs,
  five HTML plots, seven agent audit JSON files; ZIP behavior is exercised by
  offline tests. Streamlit root and health endpoints returned HTTP 200.
- Existing statistical tests use NumPy/SciPy or analytical synthetic references;
  this audit added regressions for model ordering, rank, covariance, constant
  correlations, UI regeneration, provider-check behavior and export safety.

## Provider / privacy

The sidebar configuration check never claims a successful request. An optional
**Show optional provider connectivity check** reveals a button that sends one
minimal request with no dataset (billable, no retries, 30-second timeout); a
nonempty reply does not prove structured reports work. Neither this check nor
live structured reports were tested against Baseten here. Live interpretation
sends a bounded summary including filenames, column names, question, cleaning,
units, fit and statistics; raw rows are not intentionally sent. Sensitive text
may still appear in names or summaries. Inspect data and provider terms first.
A checkbox explicitly requests a fresh live report rather than reusing a cached
one. Do not expose `.env`, keys, screenshots or sensitive data.

## Security checklist and limits

- `.env` and Streamlit secrets are ignored; `.env.example` contains placeholders.
  No tracked `.env` was found in the current tree. A complete historical secret
  scan and dependency vulnerability audit were **not performed**; if a real
  credential was previously shared, rotate it.
- Agent tools are allowlisted; model output is not executed as code. Input and
  provider output remain untrusted. Formula-injection escaping is a mitigation,
  not a guarantee for every spreadsheet application. Plot HTML loads external
  Vega dependencies; offline PNGs do not require them.
- Export provenance remains incomplete: the general result record does not
  consistently record all dependency versions and all AI request failures.
  Fingerprints identify input bytes, not real-world source authenticity.
- Timeouts bound waiting but do not guarantee interruption of running Python
  threads. Nonlinear optimization, model comparisons across differing retained
  observations, measurement-error assumptions and weighted AIC require human
  review. No universal scientific validity, privacy or security guarantee.

## Demo checklist

1. Launch `python -m streamlit run general_app.py`; use the synthetic
   `data/demo/linear_calibration_demo.csv`, not confidential data.
2. Show quality/cleaning, select `time_s` and `signal_mV`, fit the line and
   distinguish computed metrics from hypotheses. Run the bounded agent only
   after explicit consent.
3. Show the labelled **OFFLINE MOCK — NOT AI**. If a real provider request
   succeeds, show it separately and call it unverified interpretation; otherwise
   state that live integration is blocked.
4. Download and inspect JSON, cleaned CSV and ZIP; confirm the displayed data,
   settings and report match. Do not display secrets. Verify current results in
   your environment rather than assuming this machine's test counts apply.
5. For Windows setup and the timed sequence see `docs/LIVE_DEMO_GUIDE.md`; for
   models, assumptions and input limits see `docs/SCIENTIFIC_VALIDATION.md` and
   `docs/GENERAL_PLATFORM.md`.

## Not verified / remaining work

Live provider connectivity, entitlement, rate limits and structured generation;
Windows/macOS execution in this session; current remote CI for these unpushed
changes; exhaustive format/edge-case coverage; independent external scientific
validation; full dependency and historical-secret audit. The general schema
needs fuller software-version and explicit failed-AI provenance coverage.
Do not imply any of these have passed.
