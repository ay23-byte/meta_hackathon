# LabLens AI 2.0 — implementation and verification roadmap

Audit started 29 October 2026 on `arena/6c5c1264-meta_hackathon`, clean at
`0cb3381`. Existing architecture, README, provider, research assistant,
uncertainty, theory, checkup, tests, dependency bounds and CI inspected.
Baseline Linux/CPython 3.11: **550 passed, 2 skipped** (live provider), Ruff
and pip check pass. A green suite is not a scientific or security certificate.

| Requirement | Status | Evidence / verification and remaining work |
| --- | --- | --- |
| CSV/TSV ingestion, cleaning, statistics, plots, fit and diagnostics | Implemented and verified offline | `data_io.py`, `cleaning.py`, `fitting_core.py`; ingestion, numerical and plotting tests. Bounded delimited formats only. |
| Evidence IDs and deterministic insight paths | Partially implemented | `result_schema.evidence_index`, `insight_engine.py`, `tests/test_insight_engine.py`; ID existence is not semantic claim verification and report evidence is not yet a complete unified ledger. |
| Uncertainty | Partially implemented | `uncertainty_engine.py`, `tests/test_uncertainty_*`, `tests/test_prediction_intervals.py`; unweighted linear intervals and independent first-order calculator; general covariance and Monte Carlo not implemented. |
| Experiment comparison | Partially implemented | `experiment_comparison.py`, `tests/test_experiment_comparison.py`; two explicitly mapped datasets, descriptive means only, not full experiment management or inferential comparison. |
| Theory validation | Partially implemented | `theory_engine.py`, `tests/test_theory_engine.py`; user-confirmed Ohmic educational chapter, not broad tested theory registry or general prediction/observation validation. |
| AI validation and provider | Partially implemented | `ask_muse.py` and provider tests validate schemas and evidence ID allowlists; numerical and semantic claim support is not independently verified. |
| JSON/CSV/Markdown/ZIP and software versions | Implemented and verified offline | `result_schema.py`, `tests/test_result_schema.py`, `tests/test_export_safety.py`; not a complete reproducibility manifest. |
| PDF export | Not implemented | No PDF artifact or PDF-open regression test; do not claim support. |
| Literature retrieval and verification | Blocked | External retrieval host access/usable source not available in this sandbox; no references were retrieved or verified. |
| Live Muse Spark | Blocked | Two live tests skipped by default; no authorized successful live request in this session. |
| End-to-end demo and browser | Implemented but incompletely verified | Previous session documented one Linux headless Chromium path; this session must independently check startup and available smoke paths. Demo does not yet cover all requested features. |
| Broad security/performance, Windows and scientific certification | Implemented but incompletely verified | Existing safety tests and cross-platform CI configuration; no formal audit, current local Windows test, impact study, or universal correctness claim. |

## Execution order

A/B: audit, baseline and correctness checks. C: strengthen evidence traceability
and make supporting values inspectable in existing result/UI/exports. D–H:
add carefully bounded uncertainty, comparison, theory, AI guard and reports
where supported; preserve explicit limitations when an item is not finished.
I: do not invent literature. J: re-run targeted tests, full suite, lint, app
smoke, review diffs, and record exact outcomes. Do not commit or push.

## Current increment — evidence, AI guard and manifest

- **Evidence traceability: partial, tested offline.** `evidence_trace.py`
  creates an analysis fingerprint, IDs for actual non-null deterministic
  paths, missing-path notices and insight-to-evidence links. The UI exposes
  the ledger; JSON and Markdown/ZIP export it. Optional comparison, prediction
  and theory summaries are included when present. The explicitly bundled demo
  is labelled synthetic; other data provenance is not independently verified.
  IDs change when core analysis settings/results change. The compact AI
  evidence index actually sent to the provider is preserved with reports, so
  AI claim IDs can be resolved. Tests: `tests/test_evidence_trace.py`,
  `tests/test_insight_engine.py`, `tests/test_result_schema.py`.
- **Hallucination guard: partial, tested with mock clients.** `ai_guard.py`
  checks explicit `slope`, `intercept`, R², RMSE and n assignments against
  current fit values and checks claim ID membership. Contradictions are
  rejected in the provider adapter, general UI and general CLI while local
  results remain available. Matching numbers use a small rounding tolerance.
  This is not semantic entailment, unit validation, citation verification or
  comprehensive extraction: unsupported text and evidence-to-claim meaning
  remain unverified. Existing legacy contexts without ID registries are kept
  compatible and explicitly labelled unverified. Tests: `tests/test_ai_guard.py`,
  `tests/test_ask_muse_provider.py`, `tests/test_report_provenance.py`.
- **Reproducibility: partial, tested offline.** `manifest.json` in the ZIP and
  general CLI output contains source checksum/schema, selected roles/settings,
  selected cleaning counts, package versions, provider mode, evidence
  fingerprint and SHA-256/size of exported artifacts. It excludes its own
  hash and is neither a signature nor a full environment lock; selected
  filenames, column names and units can be sensitive. Existing core artifacts
  cannot be overwritten by additional chart names. Tests:
  `tests/test_reproducibility_manifest.py`, `tests/test_export_safety.py`.
- **Still incomplete:** general covariance/Monte Carlo/sensitivity and
  uncertainty-aware significance; multi-experiment management and inference;
  theory prediction validation; unit-aware and semantic AI checking; verified
  literature; PDF; integrated end-to-end demo. No externally retrieved source
  or genuine live model response is asserted. Do not label these complete.

## Verification for this increment (29 October 2026)

- Initial baseline: **550 passed, 2 skipped**, Ruff and pip check passed.
- Targeted evidence/AI/manifest/provider/UI suites passed. The first full run
  found one report-preview regression (560 passed, 1 failed, 2 skipped); the
  evidence section was moved after the existing report content rather than
  weakening the test. Focused regression then passed 26 tests.
- Final full offline run: **561 passed, 2 skipped** (live-provider tests require
  opt-in); pip check, Ruff, compileall and `git diff --check` passed.
- Started Streamlit on 0.0.0.0:8501; root and health returned HTTP 200. Linux
  headless Chromium selected the bundled synthetic demo, checked the evidence
  panel, generated the explicitly labelled offline mock, downloaded the ZIP,
  and verified every artifact checksum in `manifest.json`. No JavaScript page
  errors were recorded. This is a narrow scripted path, not a manual full
  workflow, Windows test, accessibility review or live AI call.
- Offline agent demo: all seven expected states. No live provider request,
  external literature retrieval, PDF export or Windows execution was made.
  The broader features listed as partial/not implemented/blocked remain so.
