# Scientific upgrade progress — 28 October 2026

## Completed and verified locally

- Phase 0: inspected the repository and provider/state/export paths, established **455 passed, 2 skipped**, and recorded `docs/UPGRADE_AUDIT.md`.
- Foundation and a limited Phase 2 increment: reused the current result schema and opt-in research context; implemented an explicitly conditional offline Ohmic theory chapter, symbol/units table, algebraic steps, labelled illustrative example, selected-level emphasis, mixed-unit conversion, completeness status and export integration. It preserves the original deterministic fit and makes no external calls.
- Tests: `python -m pytest -q` → **470 passed, 2 skipped**; `ruff check .` and `python -m compileall -q -x '\.venv|\.git' .` passed. Focused provider/UI/export/research run → **70 passed**. `python -m pytest -m live -q` → **2 skipped, 470 deselected**. The two live tests were not run against the provider. Streamlit root and health returned HTTP 200. Strict offline agent demo: **7/7** expected states. The sample CLI recovered slope 4.99091, intercept 0.00545455 and R² 0.999803.

## Incomplete phases and risks

This is **not** completion of the overall upgrade. The chapter covers only one confirmed model and offers conditional algebra, not textbook-depth derivations for every discipline. Existing model comparison and reliability cautions remain; no new symbolic parser, uncertainty engine or confidence intervals were added. Literature discovery/citations, PDF/OCR ingestion, document-grounded answers, scientific chat, multi-experiment comparison, full report builder/PDF/DOCX, and research evidence validation are not implemented. No externally verified source or live provider response was obtained. External literature sites and the Baseten endpoint are outside this execution environment's permitted outbound hosts. Current scientific text and assumptions require expert review; no universal scientific validation is implied.

## Exact next action

Implement a separate, bounded equation/unit layer with documented operations and analytical tests, without evaluating arbitrary user/model text. Then design explicit-consent literature retrieval with real API fixtures, source-level provenance and an offline failure path before attempting broader theoretical generation. See `docs/UPGRADE_AUDIT.md`, `docs/SCIENTIFIC_THEORY_ENGINE.md`, `docs/SCIENTIFIC_DATA_SCHEMA.md` and `docs/RESEARCH_ASSISTANT.md`.

## Current iteration — insight discovery

On `arena/ccd7a3a8-meta-hackathon`, merged PR #11 forms the starting point. Clean-tree baseline: **470 passed, 2 skipped**, Ruff and `pip check` pass. The prior chapter is an existing partial feature. Work is proceeding on deterministic insight discovery, reusing the version 2.0 result rather than introducing a competing context model. No live service calls are planned. Results and remaining work will be updated after implementation and validation.

### Delivered in current iteration

- Phase 1 is **partial**: reused the existing shared result and optional user-supplied context, and added auditable unit-origin indicators. It does not yet cover documents, literature or all proposed metadata.
- Phase 2 is **partial**: deterministic ranked insight cards now summarize available cleaning exclusions, small/saturated samples, IQR flags, selected linear fits, fit diagnostics and dataset/fit coverage. Each has evidence paths, limitations and a next step. Shared JSON and Markdown/ZIP exports include the same cards; no automatic theory or causal claims are made. See `INSIGHT_ENGINE.md`.
- Focused run: **61 passed**. Full offline suite: **478 passed, 2 skipped** (live provider tests opt-in); Ruff, compileall and `git diff --check` passed. Streamlit root and health returned HTTP 200, and AppTest exercised cards and unit correction. Strict offline agent demo returned **7/7** expected states. Bundled sample CLI recomputed 11 observations, slope 4.99091, intercept 0.00545455 and R² 0.999803; its cards were linear fit, diagnostics and coverage. No live provider call or manual browser walkthrough was performed.

### Remaining work and exact next action

The current phase covers only a conservative subset of insight types; no automatic significance or confidence ranking, change-point analysis, group differences or time-pattern discovery was added. The next phase is a small, versioned scientific model registry with at least one carefully documented model, explicit applicability/unknowns and ambiguity handling, with synthetic positive/negative tests; do not select a physical theory based on column names or fit quality alone. The remaining phases listed above (broad theory, mathematical verification, literature and PDF grounding, uncertainty beyond existing methods, chat, comparison and full reports) remain incomplete. No claim of general scientific discovery or externally verified citations is warranted.

## Current platform increment — residual diagnostics

On `arena/f82559c3-meta-hackathon` at `c7ba7dd`, the clean baseline was **487 passed, 2 skipped**. The existing dynamic CSV/plot, cleaning, statistics, fits, insight and export workflow was inspected before editing. Added a selectable residual-versus-fitted plot derived from the actual selected fit, capped and labelled, with model-assumption cautions and HTML/PNG export support. Targeted tests: **44 passed**. Final full suite: **491 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root/health returned HTTP 200, AppTest covered the plot, and all seven offline agent scenarios returned expected states. Actual-browser smoke and live provider calls were **not performed**. See `PLATFORM_IMPLEMENTATION_CHECKLIST.md` for the phase checklist, restrictions and next action; this limited diagnostic does not complete the full platform upgrade.

## Follow-up: limited offline comparison

Added an opt-in two-experiment comparison requiring mapped variables, explicit matching units and a user compatibility assertion, with summary provenance, a bounded scatter and JSON/Markdown export. Consent is invalidated by changing the files, mappings, units or first-dataset cleaning decisions. It does not automatically convert units, verify scientific compatibility, infer uncertainty, export second-dataset rows, or send comparison data to AI. Focused comparison/UI/export phase run: **59 passed**. See `EXPERIMENT_COMPARISON.md` for the exact workflow and limitations. Broader platform phases remain incomplete; no literature or live provider service has been verified.

Final follow-up regression: **499 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root/health returned HTTP 200. After the full run, an additional cleaning-difference warning was added; the focused comparison suite then passed **8 tests** and Ruff passed. An actual browser and live provider were not tested.

## Follow-up: conditional linear confidence intervals

The existing result now carries conditional 95% Student-t intervals for the slope and intercept of a successful unweighted linear fit with positive residual degrees of freedom. The UI and JSON/Markdown/ZIP exports show the method, assumptions and limits; incompatible fits report unavailable. These are not instrument or prediction uncertainties. The targeted uncertainty/fitting/statistics/schema/comparison/chart run passed **52 tests**, and Ruff passed. Weighted/nonlinear intervals, general error propagation, prediction intervals and other previously recorded phases remain incomplete. See `MATHEMATICS_AND_UNCERTAINTY.md`.

Final regression after this increment: **507 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root/health returned HTTP 200 and AppTest exercised the interval display. No live provider or actual browser was tested.

## Follow-up: bounded user-supplied error propagation

Added explicitly confirmed, first-order independent-input propagation for sum, difference, product and ratio, with unit matching for sum/difference, denominator and finite-value guards, limitations and JSON/Markdown export. Inputs are user supplied, not inferred from the uploaded data, and are not sent to AI. The targeted uncertainty/UI/export tests passed **69 tests** and Ruff passed. This is not general symbolic, correlated or Monte Carlo uncertainty propagation. See `MATHEMATICS_AND_UNCERTAINTY.md`.

Final regression after propagation: **521 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root and health returned HTTP 200; AppTest exercised the calculator. No actual browser or live provider was tested.
