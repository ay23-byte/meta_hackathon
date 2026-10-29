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
| Uncertainty | Partially implemented | `uncertainty_engine.py`, `tests/test_uncertainty_*`, `tests/test_prediction_intervals.py`; unweighted linear intervals and independent first-order calculator; two-input correlated first-order propagation and seeded bivariate-normal Monte Carlo added; arbitrary covariance matrices and general uncertainty-aware significance remain incomplete. |
| Experiment comparison | Partially implemented | `experiment_comparison.py`, `tests/test_experiment_comparison.py`; two explicitly mapped datasets, descriptive means and opt-in conditional Welch interval; not paired inference or full experiment management. |
| Theory validation | Partially implemented | `theory_engine.py`, `tests/test_theory_engine.py`; user-confirmed Ohmic chapter and explicitly supplied resistance prediction comparison; no broad theory registry or general validation. |
| AI validation and provider | Partially implemented | `ask_muse.py` and provider tests validate schemas and evidence ID allowlists; narrow numeric contradiction and evidence-ID checks; semantic claim support, units and citations are not independently verified. |
| JSON/CSV/Markdown/ZIP and software versions | Implemented and verified offline | `result_schema.py`, `tests/test_result_schema.py`, `tests/test_export_safety.py`; unsigned manifest includes artifact hashes and selected provenance, not a complete environment lock. |
| PDF export | Partially implemented | Opt-in text-first PDF, tested by parsing; figures are separate, layout and broad Unicode/accessibility not comprehensively verified. |
| Literature retrieval and verification | Blocked | External retrieval host access/usable source not available in this sandbox; no references were retrieved or verified. |
| Live Muse Spark | Blocked | Two live tests skipped by default; no authorized successful live request in this session. |
| End-to-end demo and browser | Implemented but incompletely verified | Linux headless Chromium covered synthetic demo, mock report and ZIP manifest in the prior increment; current increment includes targeted Streamlit UI tests and HTTP smoke. Demo does not yet cover all requested features. |
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
- **Still incomplete:** arbitrary covariance and general uncertainty-aware significance;
  broader multi-experiment management and inference; general theory prediction
  validation; unit-aware and semantic AI checking; verified literature;
  figure-embedded/accessibility-reviewed PDF; integrated end-to-end demo. No externally retrieved source
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
  external literature retrieval, PDF export or Windows execution was made in that earlier increment.
  The broader features listed as partial/not implemented/blocked remain so.

## Subsequent increment (29 October 2026)

- Added opt-in two-input correlated uncertainty propagation, bounded seeded
  bivariate-normal simulation and sensitivity, with explicit distribution and
  ratio-tail limitations; inputs, assumptions and simulation seed are exported.
- Added an optional text-first PDF (figures separately packaged), bounded by
  character and page limits, with fallback to other exports. PDF parse and
  artifact-hash regression tests use the development-only `pypdf` dependency.
- Added an opt-in conditional Welch mean-difference interval for independent
  samples. It is not paired inference and does not adjust for X or confounders.
- Added user-confirmed Ohmic predicted-versus-observed residual metrics using a
  separately supplied resistance and recognized units. It is descriptive, not
  a hypothesis test or proof of physical laws.
- Verification: targeted suites passed; complete offline suite **602 passed,
  2 skipped** (opt-in live provider); Ruff, pip check, compileall and diff
  check passed. Streamlit startup and root/health HTTP 200 on Linux. No current
  Windows run, real provider call, external literature or full interactive
  end-to-end test of all new paths. This increment is included in PR #19.
