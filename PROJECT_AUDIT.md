# LabLens AI project audit

## Scope

This audit covers the repository as it exists on branch
`arena/9e30a63a-meta-hackathon`: `app.py`, `analysis_core.py`,
`ask_muse.py`, `analyze_experiment.py`, `tests/`, `test_muse.py`,
`requirements.txt`, `README.md`, and related project files.

Baseline test run (before changes): `python -m pytest` →
**22 passed, 1 skipped** (the skip is the optional live Muse Spark test,
which needs `BASETEN_API_KEY`). After the fixes below: **26 passed, 1
skipped**.

## Architecture and data flow

CSV upload (or bundled sample) → row preview → user-confirmed current/voltage
columns and units → `analysis_core.prepare_analysis_data` (numeric conversion,
invalid-pair exclusion, source-row tracking) →
`analysis_core.analyze_linear` (ordinary least squares `V = mI + b`, fitted
values, residuals, R², RMSE) → plots and metrics → optional user-triggered
Muse Spark interpretation via `ask_muse.generate_interpretation` → strict
schema validation → Markdown/CSV/JSON exports. The CLI (`analyze_experiment.py`)
shares the same numerical core.

## Current features and user journey

1. Welcome/hero with value proposition and scientific safeguards.
2. CSV upload or automatic bundled sample load.
3. Column selection with alias suggestion and manual fallback; units input.
4. Paired-row cleaning with retained/dropped counts and source-row mapping.
5. OLS fit: slope, intercept, R², RMSE, fit plot, residual plot.
6. Data-quality warnings (too few points, constant voltage, non-varying current).
7. Hypothetical follow-up explorer with extrapolation flags.
8. Reproducible analysis record (JSON record, SHA-256 input fingerprint).
9. Optional Muse Spark interpretation, schema-validated.
10. Markdown, cleaned-CSV, and JSON downloads.

## Imports and exports verified

`app.py` imports from `analysis_core`:
`analyze_linear`, `detect_candidate_columns`, `prepare_analysis_data`,
`propose_measurements`, `serialize_analysis_exports` — all exist.
`app.py` lazily imports `generate_interpretation` from `ask_muse` only when
the user requests AI interpretation — exists.
`ask_muse.py` exports `REQUIRED_TITLES`, `build_prompt`, `describe_provider_status`,
`validate_report`, `generate_interpretation` — all exist.
`validate_report` enforces exactly the 8 required section titles, each once,
at most two claims, and all six claim fields.

## Findings

### Fixed in this session

| Severity | Issue | Fix |
|----------|-------|-----|
| Critical | Missing `.env.example` referenced by README and setup docs | Created `.env.example` with placeholder `BASETEN_API_KEY` only |
| High | Pandas 3.x deprecation: `DataFrame.rename(..., inplace=True)` will become an error | Replaced with assignment (`clean = clean.rename(...)`) in `analysis_core.py` and `app.py` |
| High | Duplicate column names were silently dropped by pandas before validation, causing silent data loss | `prepare_analysis_data` now raises a clear `ValueError` naming duplicated columns |
| High | Streamlit `use_container_width=True` deprecated in Streamlit 1.66 (removed after 2025-12-31) | Migrated four `st.dataframe` calls to `width="stretch"` |
| Medium | `test_muse.py` silently skipped when the provider returned empty/malformed output even with credentials | Empty/malformed output with a configured key is now a hard `pytest.fail`; call uses a bounded 30s timeout |
| Medium | AI report validation in `app.py` was looser than `ask_muse.validate_report` | Harmonized: app now requires the 8 required section titles and all six claim fields |
| Medium | No visible AI-provider status in the UI | Added provider-status panel (configured/not configured, model, endpoint) and workflow steps to the sidebar |
| Low | Documentation lived at the root with no `docs/` structure | Moved `ARCHITECTURE.md`, `SCIENTIFIC_VALIDATION.md`, `DEMO_SCRIPT.md`, `EVALUATION_PLAN.md`, `HACKATHON_PITCH.md` into `docs/`; added `docs/HACKATHON_CHECKLIST.md` |

### Tests added

- `tests/test_analysis_core.py::test_duplicate_column_names_are_rejected`
- `tests/test_pipeline_extended.py::test_generate_interpretation_requires_api_key_and_is_secret_free`
- `tests/test_pipeline_extended.py::test_export_row_counts_and_metrics_match_analysis`
- `tests/test_pipeline_extended.py::test_app_ai_report_validation_enforces_required_schema`

### Remaining / unresolved

- **Live Muse Spark integration is unverified in this environment.** No `BASETEN_API_KEY` is present, so `test_muse.py` is skipped. Earlier direct Baseten calls returned usable content (`"Hello World"`, populated `reasoning_content`) but also some incomplete fragments, so the full structured-report workflow should be re-verified live with a real key before the demo. Do not present mock output as live.
- **Straight-line fit only.** Nonlinear or weighted models, confidence intervals, parameter standard errors, and instrument uncertainty are not implemented and are explicitly labeled as unavailable. Do not present R² as proof of causation.
- **OpenAI SDK major version.** `requirements.txt` says `openai>=1.50` while the installed/tested SDK is 3.x. `ask_muse.py` is compatible with 3.x (verified: `max_retries`, `timeout`, `message.content` all work). Pin or bound the SDK in `requirements.txt` before release if a specific major version is desired.
- **Analysis artifacts (`results/`) are committed to the repo.** They are sample/demo outputs; consider gitignoring generated outputs before submission if they should not be versioned.
- **Hackathon rules.** The official Meta hackathon rules, judging criteria, deadlines, and submission requirements have not been verified against this repository; confirm authorization, required Meta technology use, and submission format separately.

## Verified behavior

- CSV parsing errors, empty files, bad encodings, malformed rows → clear user-facing errors; app stops gracefully.
- Numeric conversion with explicit dropped-row counts; NaN/infinite values excluded as invalid pairs; source row order preserved.
- Constant independent variable rejected; undefined R² when voltage has no variance.
- JSON exports are standards-compliant; non-finite numbers become `null`.
- Missing `BASETEN_API_KEY` → `RuntimeError` from `generate_interpretation`, no secret in the message.
- Provider HTTP errors (401/403/404/429) mapped to actionable, secret-free messages.
- App and deterministic analysis remain fully usable with no API key.
