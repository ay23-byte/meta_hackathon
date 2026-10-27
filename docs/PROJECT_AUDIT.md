# LabLens AI — project audit (baseline before this work)

Date: 27 Oct 2026. Branch: `arena/0c535455-meta-hackathon`.
Baseline commit: `db9f0dc` (merge of PR #3 into `main`).

This audit was written **before** any modification on this branch. Every number
below was measured in this workspace with the commands shown. Nothing here is
inferred from documentation or from an earlier session.

## 1. How the baseline was measured

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/python -m compileall -q -x '\.venv|\.git' .
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -m live -q
.venv/bin/python -B run_agent_demo.py --case all --strict --output-dir /tmp/baseline_demo
.venv/bin/python -B analyze_dataset.py data/sample_voltage_current.csv \
    --x current_A --y voltage_V --output-dir /tmp/baseline_cli
```

Installed versions (Python 3.11.2): Streamlit 1.66.1, pandas 3.1.0,
numpy 2.4.6, SciPy 1.17.1, Altair 6.3.0, matplotlib 3.11.2,
openai 3.39.0, pytest 9.1.1.

| Check | Observed baseline result |
| --- | --- |
| `ruff check .` | All checks passed |
| `compileall` | exit 0 |
| `pytest -q` | **327 passed, 2 skipped** in 61.67 s |
| `pytest -m live -q` | 2 skipped, 327 deselected (no `BASETEN_API_KEY`) |
| Agent-module coverage | 89% (734/825 statements across `agent_core`, `agent_tools`, `agent_planner`, `agent_diagnostics`, `agent_audit`) |
| `run_agent_demo.py --case all --strict` | exit 0; 5/5 cases match expected states |
| CLI sample run | slope 4.99091, intercept 0.00545455, R² 0.9998029591946405, 11 rows; 16 files written (6 top-level CSV/JSON/Markdown + 10 plot files) |

**No baseline test failures existed.** Therefore any failure observed later in
this branch is newly introduced by our own changes and must be fixed by us.

## 2. Actual application entry point

The primary, general-purpose entry point is **`general_app.py`** (Streamlit,
steps A–G plus an opt-in bounded-agent section). `app.py` is the preserved
legacy voltage–current dashboard. The headless counterparts are
`analyze_dataset.py` (general) and `analyze_experiment.py` (legacy).
`run_agent_demo.py` is a CLI demonstration driver, not an app entry point.

Correct launch commands (verified by AppTest and an HTTP smoke test in earlier
sessions; re-verified on this branch):

```bash
python -m streamlit run general_app.py     # primary app
python -m streamlit run app.py             # legacy sample workflow
```

## 3. Existing architecture

```
data_io.py            robust delimited import, encoding/delimiter sniffing,
                      SHA-256 provenance, 3-way numeric coercion
column_inference.py   per-column kinds + role suggestions
cleaning.py           previewable, consent-driven cleaning; __numeric__ companions
statistics_core.py    descriptive stats, correlations, covariance, t-CIs, IQR flags
fitting_core.py       linear/polynomial/exponential/log/power, weights,
                      model comparison, extrapolation flags
visualization_core.py 10 Altair chart types + Matplotlib PNG fallback
domain_modules.py     opt-in generic/ohmic/calibration/growth interpretation
result_schema.py      single v2.0 result object, ai_context, Markdown, exports
ask_muse.py           Muse Spark (Baseten) client + strict report validation
agent_tools.py        closed 10-tool registry with declarative param validation
agent_planner.py      Muse Spark plan request, strict validate_plan, offline
                      fallback, numeric grounding check
agent_diagnostics.py  deterministic PASS/POOR_FIT/FAILED/INSUFFICIENT verdicts
agent_audit.py        AgentRun -> JSON / JSONL / Markdown / Mermaid
agent_core.py         bounded state machine
general_app.py        Streamlit A–G + opt-in agent section
analyze_dataset.py    CLI sharing the deterministic modules
```

Data flow: upload → `read_csv_robust` → `infer_columns` → `suggest_roles` →
user overrides → `build_plan`/`preview_cleaning`/`apply_cleaning` →
`paired_values` → statistics/fits/plots/domain → `build_result` (v2.0) →
`ai_context` → optional `ask_muse` → `export_bundle`.

## 4. Working features (supported by evidence)

- **Ingestion.** `tests/test_data_io.py` and `tests/test_encoding_fallback.py`
  cover BOM/UTF-8/cp1252/latin-1, delimiter sniffing, duplicate headers,
  ragged rows, invalid/missing/non-finite distinction, and size limits.
- **Cleaning.** `tests/test_cleaning.py` verifies that invalid values are not
  coerced to zero, that rows are retained, and that cleaning is previewable.
- **Statistics and fitting.** `tests/test_statistics_core.py` and
  `tests/test_fitting_core.py` recover known parameters on synthetic data,
  including weighted fits and structured failure cases.
- **Plots.** `tests/test_visualization_core.py` covers all 10 chart types and
  the PNG fallback.
- **Exports.** `tests/test_result_schema.py`, `tests/test_analyze_dataset.py`
  and `tests/test_agent_demo.py` verify JSON/CSV/Markdown/HTML/PNG/ZIP outputs.
- **Provider.** `tests/test_ask_muse_provider.py` uses a fake OpenAI-compatible
  client for request shape, parsing, sanitization, HTTP error mapping, JSON-mode
  fallback, missing key and size limits. `tests/test_ask_muse_sections.py`
  covers configurable report sections.
- **Agent.** `tests/test_agent_*.py` (7 files, 98 tests with encoding tests)
  verify plan validation, tool dispatch, diagnostics, retries, audit trail,
  UI and the five-case demo.
- **UI.** `tests/test_general_app.py` and `tests/test_streamlit_app.py` use
  Streamlit `AppTest` on both apps.
- **CI.** `.github/workflows/ci.yml` runs lint, coverage tests and
  byte-compilation on Ubuntu/Windows × Python 3.11/3.12. PR #2 and PR #3 both
  finished 4/4 green.

## 5. Incomplete features / gaps found

1. **No `docs/PROJECT_AUDIT.md`.** The existing root `PROJECT_AUDIT.md` is a
   historical audit of the pre-refactor `app.py` only; it does not cover the
   general platform or the agent.
2. **The agent never receives the research question.** `OrchestratorConfig`
   has no `question` field; the agent cannot ask for clarification when the
   question is ambiguous, and `question` collected in step C is used only in
   the deterministic result metadata. Phase 4 steps 1 and 3 and Demo D are
   unimplemented.
3. **No Demo E (provider unavailable).** `run_agent_demo.py --use-ai` without
   a key silently switches to the offline planner; there is no reproducible
   case that injects a provider failure and shows that offline features
   survive. There is also **no deterministic offline mock report** that is
   explicitly labelled as a mock (Phase 3 requirement 10).
4. **Report sections do not match the requested structured scientific
   report.** `ask_muse.SECTION_REGISTRY` has 10 titles (8 legacy defaults +
   2 optional). Titles such as "Research Question", "Dataset Overview",
   "Analysis Performed", "Model-Fit Assessment" and "Recommended Next
   Investigation" are absent. The legacy 8-title default must be preserved.
5. **Claims have no machine-readable result IDs.** `validate_report` keeps six
   string claim fields; quantitative claims cannot be traced to a specific
   computed result ID.
6. **No bounded retry for transient provider failures.** `generate_interpretation`
   retries once only on HTTP 400 (request-shape fallback). 429/408/5xx
   responses are reported but not retried with a bounded backoff.
7. **Tool registry is missing required operations.** Phase 4 asks for
   "compare supported models", "produce a structured evidence summary",
   "assess data quality" and time-series analysis. The 10 existing tools
   cover inspect/profile/describe/correlate/outlier/fit/diagnose/plot/
   confirmation/insufficient, but not model comparison, evidence summarising
   with result IDs, or time-series summaries.
8. **Provider status in the UI is a single sidebar line.** It does not show
   mode (live / offline fallback / labelled mock) or the outcome of the last
   provider call.
9. **Windows documentation is thin.** The README has a short PowerShell block
   but no troubleshooting, no secure `.env` procedure in PowerShell, no
   exact test/demo commands for Windows, and no honest per-feature status.
10. **Hackathon materials predate the agent.** `docs/HACKATHON_PITCH.md`,
    `docs/DEMO_SCRIPT.md` and `docs/HACKATHON_CHECKLIST.md` describe the
    original linear-fit app; they need updating to reflect the actual agent,
    the five (soon seven) demo cases and the measured verification.

## 6. Known bugs

- No failing tests at baseline, and no known correctness bug in the numerical
  core. The two skipped tests are intentional opt-in live-provider tests.
- A previous Windows CI failure (PR #3) came from `time.monotonic()`
  resolution in a test; it was fixed with `max_wall_s=-1`. CI now emits
  `::error::` annotations from `junit.xml` for future diagnostics.
- **Fragility (not a current failure):** a workspace snapshot once re-encoded
  the checked-in cp1252 example to UTF-8; encoding fallback tests now generate
  their bytes in memory, so this should not recur.

## 7. Security and reliability risks

| Risk | Current mitigation | Residual concern |
| --- | --- | --- |
| AI-generated code execution | `agent_tools` is an exact-key registry; `validate_plan` rejects forbidden tokens; static test asserts no `eval(`/`exec(`/etc. | New tools must follow the same pattern. |
| Credential exposure | `BASETEN_API_KEY` read from env/`.env`; `.env` gitignored; errors redacted. | User must never paste a key into chat or a file. No live key here. |
| Oversized/untrusted data | 5 MiB/200k row bounds in app, 50k/20 col in agent; per-tool 5 s, 30 s run. | Timed-out tool threads are abandoned, not killed (documented). |
| Unbounded retries | 2 retries, 3 fit attempts, 8 steps. | Provider-level 429/5xx retries still need a bound. |
| Silent data loss | Invalid rows retained; cleaning is consent-driven. | Duplicate removal remains an explicit user opt-in. |
| Misleading AI output | Numeric grounding check; strict report schema. | Claims lack result IDs; mock output must never be labelled as live. |

## 8. Tests that currently pass or fail

- **Pass:** 327 tests across 27 test files; `ruff`, `compileall` clean.
- **Skipped (2):** `test_muse.py` live-provider tests, because
  `BASETEN_API_KEY` is not configured. `-m live` selects only those 2.
- **Fail:** none at baseline.

## 9. Missing integration tests

- No test that a **research question** changes agent behaviour (clarification
  gate, stated assumptions in the audit trail).
- No test that a **provider outage** leaves the app usable and never labels a
  mock as a real response.
- No test for the **scientific report profile** end-to-end (prompt → validated
  report → Markdown export).
- No test for **claim result-ID grounding**.
- No test that **transient provider retries** are bounded.
- No test for the new registry tools (`compare_models`, `evidence_summary`,
  `time_series_summary`) at tool level and in an orchestrated run.
- No Windows-specific path/encoding test for exports (CI covers compilation
  and tests, not artifact filenames on Windows).

## 10. Prioritized implementation plan

1. Create this audit; record baseline numbers (done).
2. Add deterministic **offline mock report** + honest provider status/mode;
   add bounded transient retries and a second **scientific report profile**
   with optional claim result IDs, preserving the legacy default.
3. Add a **research-question clarification gate** to the orchestrator,
   including the question in the audit trail and UI/CLI wiring.
4. Extend the **tool registry** with model comparison, evidence summary and
   time-series summary (validated, bounded, tested).
5. Add **Demo D** (ambiguous question) and **Demo E** (provider unavailable,
   mock clearly labelled) using real project functions; keep `--strict`.
6. Wire UI/CLI: question, report profile, mock toggle, provider status.
7. Add focused tests for each change; run full suite, lint, compileall, demo,
   AppTest and an HTTP startup smoke test.
8. Update `docs/ARCHITECTURE.md`, `docs/AGENT_WORKFLOW.md`,
   `docs/SCIENTIFIC_VALIDATION.md`, `docs/DEMO_SCRIPT.md`,
   `docs/PROVIDER_INTEGRATION.md`, README (Windows), and hackathon materials.
9. Final honest report: commands, exact counts, what is live-verified vs
   mocked, remaining blockers.

---

# Resolution log — master-prompt phase (27 Oct 2026)

The sections above are the **baseline audit**, deliberately left intact. This
log records what was actually changed and verified afterwards. It does not
claim that every gap is closed; live provider behaviour remains unverified.

## Implemented in code

| Baseline gap | Change | Verification |
| --- | --- | --- |
| No research question / Demo D | `OrchestratorConfig.research_question`, question event, deterministic `clarify_question()` gate, clarification options in audit/Markdown/UI, question in plan prompt and AI digest | `tests/test_master_prompt_features.py`, demo D |
| No provider-unavailable Demo E | `run_agent_demo.py` case E forces both AI seams to fail, records fallback, writes `provider_status.json` + `offline_mock_report.md` | demo E, `tests/test_agent_demo.py` |
| No explicitly labelled offline mock | `ask_muse.generate_mock_report()` separate from live path; UI button and CLI `--ai-mock`; labelled in JSON/Markdown/UI | `tests/test_master_prompt_features.py`, `tests/test_general_app.py`, `tests/test_analyze_dataset.py` |
| Missing scientific report section names | `ask_muse.REPORT_PROFILES` with independent `scientific` registry; `section_registry()`; UI/CLI profile selector | `tests/test_master_prompt_features.py` |
| Claims lacked result IDs | `result_schema.evidence_index()`, `ai_context(result_ids/evidence_index/research_question)`, strict `validate_report(allowed_evidence_ids=...)`, prompt rule | `tests/test_master_prompt_features.py`, `tests/test_result_schema.py` |
| No bounded transient retries | `ask_muse._request_with_bounded_retries()` for 408/429/5xx and transport errors; bounded backoff; 400 compatibility fallback retained | `tests/test_master_prompt_features.py`, `tests/test_ask_muse_provider.py` |
| Thin provider status | `ask_muse.provider_status()` (no network call, `live_verified=False`), sidebar expander and step F caption | `tests/test_master_prompt_features.py`, AppTest |
| Registry lacked three tools | Added validated `compare_models`, `evidence_summary`, `time_series_summary`; default offline plan now 8 steps | `tests/test_agent_tools.py`, demo A-E |
| AI/mock separation in exports | `markdown_report()` distinct headings, disclaimers and computed-result-ID lines; `results.json` retains `source`/`is_mock` | `tests/test_result_schema.py`, CLI smoke |
| CLI/UI question plumbing | `--question`, `--agent-question`, `--report-profile`, `--ai-mock`; UI uses existing Scientific question input | `tests/test_analyze_dataset.py`, `tests/test_agent_ui.py` |

## Measured results after implementation

```text
.venv/bin/ruff check .                       -> All checks passed
.venv/bin/python -m compileall ...           -> exit 0
.venv/bin/python -m pytest -q                -> 348 passed, 2 skipped in ~70 s
.venv/bin/python -m pytest -m live -q        -> 2 skipped, 348 deselected
.venv/bin/python -B run_agent_demo.py --case all --strict
                                            -> 7/7 expected states OK
.venv/bin/python -B analyze_dataset.py data/sample_voltage_current.csv --x current_A --y voltage_V --output-dir /tmp/final_cli
                                            -> 16 files; slope 4.99091, intercept 0.00545455, R² 0.9998029591946405
.venv/bin/python -B analyze_dataset.py data/sample_voltage_current.csv --x current_A --y voltage_V --ai-mock --report-profile scientific
                                            -> labelled mock in report.md/results.json
.venv/bin/python -m pytest -q --cov=ask_muse --cov=result_schema --cov=agent_* --cov=run_agent_demo
                                            -> 92% (1,441/1,574 statements) across those 8 modules
```

## CI verification

PR #4 ran `.github/workflows/ci.yml`; `gh pr checks 4 --watch` reported all four
matrix jobs passing (Ubuntu/Windows x Python 3.11/3.12). This verifies the
offline suite and lint on both operating systems, not live Muse Spark access.

## Remaining honest limits

- No `BASETEN_API_KEY` is configured in this sandbox. Live Muse Spark
  reachability, quota, real response shape, and a genuinely AI-proposed plan
  driving a real agent run are **unverified**. `pytest -m live -q` skips.
- The offline mock is a deterministic template, not an AI model output. It is
  labelled everywhere it is exported or displayed.
- Support remains delimited text/CSV with dot decimals; no arbitrary scientific
  formats, no causal inference, no automatic domain detection.
- `provider_status()` reports configuration, not reachability. A key being set
  is never presented as proof that live AI works.
