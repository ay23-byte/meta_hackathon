# Scientific upgrade progress — 28 October 2026

## Completed and verified locally

- Phase 0: inspected the repository and provider/state/export paths, established **455 passed, 2 skipped**, and recorded `docs/UPGRADE_AUDIT.md`.
- Foundation and a limited Phase 2 increment: reused the current result schema and opt-in research context; implemented an explicitly conditional offline Ohmic theory chapter, symbol/units table, algebraic steps, labelled illustrative example, selected-level emphasis, mixed-unit conversion, completeness status and export integration. It preserves the original deterministic fit and makes no external calls.
- Tests: `python -m pytest -q` → **470 passed, 2 skipped**; `ruff check .` and `python -m compileall -q -x '\.venv|\.git' .` passed. Focused provider/UI/export/research run → **70 passed**. `python -m pytest -m live -q` → **2 skipped, 470 deselected**. The two live tests were not run against the provider. Streamlit root and health returned HTTP 200. Strict offline agent demo: **7/7** expected states. The sample CLI recovered slope 4.99091, intercept 0.00545455 and R² 0.999803.

## Incomplete phases and risks

This is **not** completion of the overall upgrade. The chapter covers only one confirmed model and offers conditional algebra, not textbook-depth derivations for every discipline. Existing model comparison and reliability cautions remain; no new symbolic parser, uncertainty engine or confidence intervals were added. Literature discovery/citations, PDF/OCR ingestion, document-grounded answers, scientific chat, multi-experiment comparison, full report builder/PDF/DOCX, and research evidence validation are not implemented. No externally verified source or live provider response was obtained. External literature sites and the Baseten endpoint are outside this execution environment's permitted outbound hosts. Current scientific text and assumptions require expert review; no universal scientific validation is implied.

## Exact next action

Implement a separate, bounded equation/unit layer with documented operations and analytical tests, without evaluating arbitrary user/model text. Then design explicit-consent literature retrieval with real API fixtures, source-level provenance and an offline failure path before attempting broader theoretical generation. See `docs/UPGRADE_AUDIT.md`, `docs/SCIENTIFIC_THEORY_ENGINE.md`, `docs/SCIENTIFIC_DATA_SCHEMA.md` and `docs/RESEARCH_ASSISTANT.md`.
