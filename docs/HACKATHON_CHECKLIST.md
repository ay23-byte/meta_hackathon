# LabLens AI — Hackathon submission checklist

Only items verified in this environment are checked. See
`docs/HACKATHON_RULES.md` for the source of each official requirement and
`docs/PROVIDER_INTEGRATION.md` for the live-integration status.

## Acceptance criteria

- [x] The app imports and starts successfully (`AppTest`, plus a Streamlit
      server smoke test returning HTTP 200)
- [x] Sample data loads (bundled `data/sample_voltage_current.csv`, 11 rows)
- [x] Invalid data is handled transparently (excluded-row counts shown)
- [x] Scientific calculations are deterministic and tested (112 offline
      tests, independent `lstsq` oracle)
- [x] Graphs and metrics match the underlying analysis (CLI artifact test,
      AppTest metric assertions, residual identity)
- [x] AI generation handles missing credentials and provider errors
- [x] Empty, malformed, oversized, and truncated model responses are rejected
- [x] Valid reports satisfy the application's schema (8 sections, 6 claim
      fields, size limits; single validator shared by producer and UI)
- [x] Reports correspond to the currently selected dataset (SHA-256 context
      hash including the provider model)
- [x] Exports are consistent with displayed results (JSON/CSV/Markdown)
- [x] No secret is exposed in source control, UI, logs, or exports
- [x] Standard offline test suite passes (`python -m pytest -q`)
- [x] Live API status is reported honestly (optional, key-dependent)
- [x] Documentation matches actual behavior
- [x] The demo script can be executed with the existing project
- [x] This checklist lists outstanding items explicitly

## Environment and setup

- [x] `requirements.txt` lists small, justified, bounded dependencies
- [x] `requirements.lock.txt` records the exact tested environment
- [x] `requirements-dev.txt` provides coverage and lint tooling
- [x] `.env.example` has placeholders only (no real key)
- [x] `.env` excluded from version control
- [x] Windows setup steps documented in `README.md`
- [x] CI workflow added for Linux + Windows / Python 3.11 + 3.12
      (`.github/workflows/ci.yml`) — **config added; GitHub Actions run not
      executed in this environment**
- [ ] Run the CI workflow on GitHub once and confirm both OS jobs pass

## Deterministic analysis (verified by tests)

- [x] CSV upload and measurement-column selection
- [x] Numeric cleaning with excluded-row counts and source-row tracking
- [x] Duplicate column names rejected (DataFrame API)
- [x] Numerically stable centred OLS `V = mI + b`: slope, intercept, R², RMSE
- [x] Observed-versus-fitted plot and residual plot
- [x] Hypothetical measurement explorer with extrapolation flags
- [x] Constant current rejected; undefined R² handled
- [x] Upload size (5 MiB) and row (200,000) limits enforced

## Muse Spark AI integration

- [x] Optional interpretation gated on explicit button press
- [x] API key never printed, logged, or exported
- [x] Missing key → clear warning, app remains usable
- [x] Provider errors mapped to actionable, secret-free messages
- [x] Empty/malformed/truncated/oversized output rejected, not treated as success
- [x] Structured report validated against the required schema
- [x] AI claims labeled as not independently verified
- [x] AI content rendered as plain text (no link/markup injection)
- [x] Developer-message + JSON-mode request with one bounded HTTP-400 fallback
- [x] `developer`/`temperature`/`max_completion_tokens` aligned with Meta's
      documented conventions
- [x] `BASETEN_MODEL` override supported for dated hackathon model IDs
- [ ] **Live end-to-end verification with a real `BASETEN_API_KEY`** (two
      opt-in live tests: connectivity and structured report)

## Reproducibility and exports

- [x] Markdown report, cleaned CSV, analysis record JSON downloads
- [x] Source filename and SHA-256 fingerprint recorded (dashboard + CLI)
- [x] Original/cleaned row counts and cleaning rules recorded
- [x] Software versions recorded in the analysis record
- [x] AI provider/model and report-generation status recorded
- [x] Generated CLI artifacts are gitignored (`results/README.md`)
- [x] CSV headers sanitized against spreadsheet formula injection

## Quality gates (measured 26 Oct 2026)

- [x] 229 passed, 2 skipped offline (skips = live tests); see `docs/IMPLEMENTATION_REPORT.md`
- [x] 98% statement coverage across the four application modules
- [x] `ruff check .` clean
- [x] All Python modules byte-compile
- [x] Streamlit AppTest covers the real UI script and upload paths

## Official rules and submission

- [x] Judging weights recorded from the Official Rules: Impact 30%,
      Meta AI Tooling 25%, Technical Depth 20%, Demo 25%
- [x] Theme fit identified ("Push the Frontier": accelerate a scientific
      experiment)
- [x] "Built with Muse Spark Open" attribution shown in the UI (Muse Model
      License requirement)
- [ ] Confirm accepted-participant status and acceptance of the Official Rules
- [ ] Confirm track, theme, team members, and Representative
- [ ] Confirm deadline (4 Nov 2026, 9:00 PM ET) in local time
- [ ] Confirm whether a public repo, a video length limit, and a
      "work only during the window" rule apply — not stated in the rules
      text we read; community guidance says yes for all three
- [ ] Confirm the Meta technology/credit requirement for the account and the
      correct Baseten model identifier
- [ ] Keep the dated git history as evidence of work done in the window
- [ ] Record and upload the demo video; add the link to the submission
- [ ] Submit through the Cerebral Valley portal before the deadline

## Demo readiness

- [x] Demo script runs with bundled sample data
- [x] Fallback path prepared when the API is unavailable
- [x] No mock response presented as a live API result
- [x] No API key shown in docs, code, or exported records
- [ ] Demo video recorded (see `docs/DEMO_SCRIPT.md`)

## Explicitly outstanding / unverified

1. Live Muse Spark round-trip: no `BASETEN_API_KEY` in this environment.
   Offline fake-client tests verify our side of the contract, not the
   provider's availability or the model's reliability in producing the
   strict JSON schema.
2. ~~GitHub Actions matrix has not been executed here.~~ **Resolved 27 Oct
   2026:** PR #2 ran the full 2x2 matrix (Ubuntu/Windows x Python 3.11/3.12);
   all four jobs passed, including lint, offline tests with coverage, and
   byte-compilation.
3. Demo video has not been recorded.
4. Eligibility, acceptance, and final submission steps are the
   participant's responsibility.
5. Scientific scope: the original `app.py` is a straight-line unweighted fit.
   The general platform (`general_app.py` / `analyze_dataset.py`) adds five
   model families, weighted fitting, Student-t CIs, and broader statistics,
   but still does not verify instrument calibration, dataset provenance, or
   causal claims. See `docs/IMPLEMENTATION_REPORT.md` for the full list.
6. Two Streamlit entry points exist: `general_app.py` (general platform,
   steps A-G) and the preserved `app.py` (original sample workflow). Decide
   which to show first in the demo.
