# Platform implementation checklist

## Audit — current session

- [x] Inspected clean branch `arena/f82559c3-meta-hackathon` at `c7ba7dd`, repository structure, dependency bounds, README and architecture, core engines, exports, provider and tests. No staged, modified, untracked or ignored user files were reported at inspection (a local ignored `.venv` was subsequently created for testing).
- [x] Established baseline: dependency check and Ruff passed; targeted plotting/statistics/fitting/schema tests **40 passed**; full offline suite **487 passed, 2 skipped** (live provider tests require explicit opt-in).
- [x] Phase 1 already partially exists: content-keyed CSV import, cleaning preview, selected-axis charts, plot downloads and tests for sequential uploads. Limitations include the two-numeric-column requirement and 50,000-point plot cap.
- [x] Phase 2 already partially exists: descriptive statistics, selected model fitting, weights only when supplied, model comparison, residual-versus-X and conditional Ohmic notes. Parameter errors do not establish instrument accuracy. New focused increment: add an explicitly labelled residual-versus-fitted diagnostic using the existing fit and residuals.
- [ ] General analytical/Monte Carlo uncertainty propagation and valid confidence intervals for all fits; do not invent instrument uncertainty.
- [ ] Phase 3: compatible multi-dataset comparison and group-level evidence with explicit variable/unit mapping. Existing insights and result provenance are a partial foundation only.
- [ ] Phase 4: comprehensive report formats, interactive grounded experiment chat, real references and document grounding. Existing Markdown/JSON/CSV/PNG/HTML/ZIP and optional validated Muse Spark reports remain available.
- [ ] Phase 5: broader UX/performance/security review and an actual browser smoke test. An HTTP health check and Streamlit AppTest alone are not a browser test.

## Safety and verification

Offline deterministic computation must stay authoritative; no raw-data or external calls without user action, no inferred physical causes, no secrets in exports, and no silent mock fallback. Fit diagnostics are indications only and depend on model/error assumptions. Preserve existing data and schema compatibility. This checklist describes implemented pieces and gaps, not a claim of a complete platform.

## Current increment — residuals vs fitted

- [x] Added a selectable residual-versus-fitted diagnostic to the existing chart engine and Streamlit chart selector, using the selected fit's paired X values, its model predictions and its own residuals. It works with existing supported fit models; it does not perform a second regression. HTML and PNG exports use the same data; output is capped at 50,000 residuals with a warning. Labels include selected Y units. The existing residual-versus-X chart remains available.
- [x] Residual patterns are described only as possible diagnostic indications; an apparently random plot does not establish model validity or error assumptions. No instrument uncertainty or causal explanation is inferred.
- [x] Phase-targeted validation: `python -m pytest -q tests/test_residual_fitted_chart.py tests/test_visualization_core.py tests/test_fitting_core.py tests/test_dynamic_plotting.py tests/test_result_schema.py` → **44 passed**. Ruff and diff whitespace check passed.
- [ ] Broader phase 2 uncertainty/error propagation, phase 3 comparison, phase 4 report/chat, and phase 5 hardening are not completed in this increment. Next action: design bounded experiment comparison with explicit user-confirmed quantity definitions and units, preserving each dataset's separate provenance; add incompatibility and synthetic-data tests before UI integration.
- [x] Final regression: full suite **491 passed, 2 skipped** (both live-provider tests); `python -m ruff check .`, `compileall` and `git diff --check` passed. Offline agent demo produced all **7 expected states**. Streamlit root and health endpoints returned HTTP 200; AppTest exercised the new chart. No real browser was available in this environment, so the actual-browser acceptance criterion is **not verified**. No live provider request was made.

## Follow-up — limited two-experiment comparison

- [x] Added an offline two-dataset descriptive comparison in the existing app. Both selected quantities, matching explicit unit strings, methods and conditions require user confirmation. There is no automatic conversion or inference of compatibility. Confirmation is bound to both source hashes, mappings, units and primary cleaning choices.
- [x] Preserve individual provenance, paired/excluded counts and paired means; show a bounded shared scatter and a labelled difference in means. The full pair set drives summaries; at most 2,000 per dataset are drawn. Comparison JSON/Markdown is included in existing exports, not AI context; the second raw dataset and comparison plot are not exported.
- [x] Focused phase tests: **59 passed** including incompatible units, missing data, cap, escaping and fresh consent. Ruff and diff check pass.
- [ ] Broader arbitrary-unit conversion, more than two experiments, uncertainty-aware comparisons, experiment history, comparison plot export, AI chat, PDF/DOCX, literature/document grounding, comprehensive theory and advanced uncertainty remain incomplete. No actual browser smoke or live service calls have been performed.
- [x] Follow-up full regression: **499 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root/health returned HTTP 200. A subsequent warning-text clarification was checked by the focused comparison suite (**8 passed**) and Ruff. No actual-browser test or live provider call was performed.

## Follow-up — conditional linear parameter intervals

- [x] Added deterministic 95% Student-t intervals for unweighted linear-fit slope and intercept, derived from the existing residual standard errors and `n − 2` degrees of freedom. Results are conditional on explicitly stated error-model assumptions, with references to the authoritative fit fields. Existing parameter values and fits are unchanged.
- [x] Missing/weighted/failed/nonlinear fits, missing finite errors and nonpositive degrees of freedom report unavailable rather than inventing uncertainty. The UI, shared JSON and Markdown/ZIP exports include the status and limitations; no API call or raw-data transmission is involved. Analytical, refusal, safety and UI tests added.
- [x] Targeted uncertainty/fitting/statistics/export/comparison/chart run: **52 passed**; Ruff passed.
- [ ] General uncertainty propagation, uncertainty for weighted and nonlinear fits, prediction intervals, scientific AI chat, verified literature, PDF grounding, broad report formats and actual-browser verification remain incomplete. More than two experiments and automatic unit conversion remain unsupported. See `MATHEMATICS_AND_UNCERTAINTY.md` for assumptions and limits.
- [x] Final regression after the uncertainty increment: **507 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root/health returned HTTP 200. AppTest exercised the interval display; no actual browser or live provider was tested.

## Follow-up — bounded first-order error propagation

- [x] Added an offline optional calculator for sum, difference, product and ratio of explicitly entered values and standard uncertainties under a zero-covariance first-order assumption. Identical units are required for sum/difference; units are otherwise user labels, not verified or converted. It refuses invalid inputs and warns about ratios with denominator near zero.
- [x] User confirmation is tied to every input; user-supplied input, method, result and limitations appear in existing JSON and Markdown/ZIP exports only when confirmed, not in AI context. Targeted uncertainty/UI/export suite: **69 passed**; Ruff passed.
- [ ] Correlated error propagation, arbitrary equations, Monte Carlo, general dimensional analysis and broader platform features remain incomplete. See `MATHEMATICS_AND_UNCERTAINTY.md`.
- [x] Final regression after propagation: **521 passed, 2 skipped**; Ruff, compileall and diff check passed. Streamlit root and health returned HTTP 200. AppTest exercised the panel; actual-browser and live-provider checks were not performed.

## Hackathon readiness increment — 28 Oct 2026

- [x] Re-audited current entry points, demo, science and export documentation;
  baseline full offline suite: 521 passed, 2 live-provider tests skipped; Ruff
  and dependency check passed. This was a focused audit, not a certification
  or a line-by-line security review of the entire repository.
- [x] Exposed the existing synthetic calibration demo in the main app without
  an upload, with an explicit synthetic-data disclaimer. Added an executable
  walkthrough and UI regression test. The dataset is not experimental evidence.
- [x] Corrected linear parameter covariance for absolute user-supplied inverse
  variances; residual scatter no longer falsely reduces known measurement
  uncertainty to zero. Unweighted two-point fits no longer invent a residual-
  based standard error. These estimates are conditional on their assumptions.
- [x] Included Python and selected package versions in JSON and Markdown (and
  thus ZIP) records, with no environment variables, paths or credentials. This
  allowlist is not a complete environment lock; the standalone CSV has no
  embedded provenance. Corrected the pitch and demo text accordingly.
- [ ] Actual browser smoke, live Muse Spark end-to-end verification, user impact
  study, demo recording and participant-portal submission remain outstanding.
  Full literature grounding, generalized uncertainty and other items above
  remain incomplete. No win, clinical utility or scientific certification is
  implied.
- [x] Final verification: focused fitting/demo/schema/UI/CLI/provider suite
  **81 passed**; full offline suite **525 passed, 2 skipped** (live-provider
  opt-in); Ruff, compileall and `git diff --check` passed. Streamlit root and
  health endpoints returned HTTP 200, and AppTest selected the demo. These
  checks are not an actual-browser walkthrough or a live-provider test.

## Follow-up — browser smoke and conditional prediction intervals

- [x] Ran a real headless Chromium browser against the running Streamlit app:
  selected the synthetic calibration file and X/Y columns, entered an in-range
  and an extrapolated candidate, generated the explicitly labelled offline
  mock, downloaded JSON and ZIP, and opened the ZIP. The JSON recorded 15
  rows, 12 fitted pairs, slope 2.5, intercept 0.1, the extrapolation flag and
  conditional intervals; the report included those intervals. No browser
  JavaScript page errors were recorded. This is one scripted Linux/headless
  path, not a comprehensive manual, Windows, mobile or accessibility review.
- [x] Added unweighted linear 95% mean-response and single-observation
  prediction intervals, with assumptions and limitations in the UI and
  JSON/Markdown/ZIP. Weighted/nonlinear/two-point fits explicitly report
  unavailable; no measured uncertainty is inferred. Analytical references,
  invalid inputs, extrapolation, exports and AppTest are covered. The CLI does
  not yet offer these intervals.
- [x] Uncertainty-column hints no longer automatically enable weighted fitting:
  the selection starts at `(none)` and the user must explicitly choose a
  column. Corrected an exponential-model description that incorrectly claimed
  its amplitude was constrained positive; the optimizer remains unconstrained.
- [ ] Live Muse Spark round trip, participant portal checks, recording and a
  user impact study still need external access or human participation. General
  uncertainty, grounded chat/literature, extended formats and broad hardening
  remain incomplete; this increment does not claim full platform completion.
- [x] Follow-up verification: focused suite **58 passed**; full offline suite
  **530 passed, 2 skipped** (live-provider tests); Ruff, compileall and diff
  check passed. The seven offline agent demo cases reached expected states.
  The Chromium scenario was rerun after the final UI change and passed.

## Follow-up — whole-project checkup (28 Oct 2026)

- [x] Reviewed the major ingestion, analysis, fitting, uncertainty, plotting,
  export, provider, agent, legacy, CI and demo paths. Documented the exact
  scope, fixes and limitations in `PROJECT_CHECKUP.md`; this is not an
  exhaustive proof or formal security/scientific audit.
- [x] Fixed CSV field errors and multiline headers, numerical underflow and
  overflow edge cases, selected-axis agent weight alignment, representability
  of supplied inverse variances, agent timeout state isolation and exception
  redaction, unsafe CLI export targets, and undefined prediction messaging.
- [x] Verification: focused agent, fit, importer, statistics, CLI/export and
  UI runs passed; final full suite **550 passed, 2 skipped** (live-provider
  tests); pip check, Ruff, compileall and diff check passed; seven offline
  agent scenarios reached expected states. Linux headless Chromium selected the
  synthetic demo, generated an offline mock, checked prediction intervals and
  downloaded JSON/ZIP; the first attempt timed out on a UI selector and the
  retry passed. Streamlit health returned HTTP 200.
- [ ] Live provider, broader browser/device coverage, remote Windows CI for
  these unpushed changes, human impact validation and submission remain
  unverified. General platform gaps remain as documented above.
