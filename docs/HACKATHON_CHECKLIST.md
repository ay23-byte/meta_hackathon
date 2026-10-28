# LabLens AI — Hackathon submission checklist

Only items verified in this environment are checked. See
`docs/HACKATHON_RULES.md` for the source of each official requirement and
`docs/PROVIDER_INTEGRATION.md` for the live-integration status.

## Acceptance criteria

- [x] The app imports and starts successfully (`AppTest`, plus a Streamlit
      server smoke test returning HTTP 200)
- [x] Sample data loads (bundled `data/sample_voltage_current.csv`, 11 rows)
- [x] Invalid data is handled transparently (excluded-row counts shown)
- [x] Scientific calculations are deterministic and tested (426 offline
      tests, independent `lstsq` oracle and synthetic known-value datasets)
- [x] Graphs and metrics match the underlying analysis (CLI artifact test,
      AppTest metric assertions, residual identity)
- [x] AI generation handles missing credentials and provider errors
- [x] Empty, malformed, oversized, and truncated model responses are rejected
- [x] Valid reports satisfy the application's schema (two strict profiles,
      6 claim fields + evidence IDs when computed IDs are supplied, size
      limits; single validator shared by producer, UI and CLI)
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
- [x] PR #4 CI: all four matrix jobs passed (Ubuntu/Windows x Python
      3.11/3.12), verified with `gh pr checks 4 --watch`

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
- [x] Bounded transient 408/429/5xx retries and a safe HTTP-400 shape fallback
- [x] Honest `provider_status()` (never claims live verification from a key)
- [x] Explicitly labelled deterministic OFFLINE MOCK path (UI button, CLI flag,
      distinct export headings); never substituted for a live response
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

## Quality gates (measured 28 Oct 2026)

- [x] 426 passed, 2 skipped offline (skips = live tests); see `docs/IMPLEMENTATION_REPORT.md`
- [x] 98% statement coverage across the four application modules
- [x] `ruff check .` clean
- [x] All Python modules byte-compile
- [x] Streamlit AppTest covers both UI scripts, upload paths and the mock button
- [x] `run_agent_demo.py --case all --strict` → 7/7 expected A-E states
- [x] `pytest -m live -q` → 2 skipped, 426 deselected (no key configured)
- [x] `pytest -q --cov=ask_muse --cov=result_schema --cov=agent_* --cov=run_agent_demo` → 92% of 1,574 statements

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
   2026:** PR #2 and PR #3 each ran the full 2x2 matrix (Ubuntu/Windows x
   Python 3.11/3.12); all four jobs passed on both, including lint, offline
   tests with coverage, and byte-compilation. PR #3's first run exposed a
   Windows-only flaky deadline test, which was fixed and re-verified.
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


## Bounded analysis agent (added 27 Oct 2026)

- [x] Observable plan -> validate -> execute -> diagnose -> retry -> interpret loop
- [x] Closed 10-tool registry; no arbitrary code execution (static + dispatch tests)
- [x] Strict plan validation before execution; rejected plan falls back
- [x] Test that validated AI plans actually change the executed tool sequence
- [x] Bounded retries, steps, wall time, dataset size and model complexity
- [x] Destructive-tool consent gate (default off)
- [x] `INSUFFICIENT_EVIDENCE` and `NEEDS_CLARIFICATION` terminal states
- [x] Deterministic numbers only; AI reports must pass a numeric grounding check
- [x] Structured audit trail (JSON / JSONL / Markdown / Mermaid) with evidence refs
- [x] Five synthetic demo cases, strict mode passing
- [x] Standard A-G pipeline remains usable with no key
- [ ] Live Muse Spark plan -> execution round trip (no `BASETEN_API_KEY` here)


---

## Hardening update (27 Oct 2026)

- [x] Provider config centralized in `provider_config.py`; no import-time
      `.env` mutation; process env wins; placeholder keys rejected.
- [x] Live tests require `pytest --run-live -m live -v`; ordinary `pytest -q`
      skips them even when a developer `.env` exists.
- [x] Six historical failures reproduced with a fake `.env` and fixed; full
      suite with fake `.env` → **426 passed, 2 skipped**.
- [x] Mocked tests cover success, missing/blank/placeholder key, 401/403/429,
      timeout, network failure, empty/invalid/unexpected response, AI disabled.
- [x] Duplicate Streamlit AI calls prevented in both apps; agent consent
      checkbox remains distinct and default-off.
- [x] Export/ZIP path traversal blocked by `safe_archive_name()`; exports are
      valid, mutually consistent and secret-free.
- [x] Scientific overflow regression fixed and documented.
- [x] Synthetic demo dataset + `docs/LIVE_DEMO_GUIDE.md` added.
- [x] PR #5 CI: all four matrix jobs passed (Ubuntu/Windows x Python
      3.11/3.12), verified with `gh pr checks 5 --watch`.
- [ ] Record the demo video and confirm current portal requirements.
- [ ] **Live Baseten end-to-end verification** remains BLOCKED without a real
      key; do not claim it passed.
