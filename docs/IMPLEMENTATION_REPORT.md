# Implementation report - general-purpose platform

Date: 27 Oct 2026. Branch: `arena/e7fb1bbb-meta-hackathon`.
Baseline at the checkpoint commit `1eeb04a`: **112 passed, 2 skipped**,
`ruff check .` clean. This report describes work added after that checkpoint.
All numbers below were measured in this workspace; nothing is extrapolated.

## What was implemented

| Phase | Modules / changes | Status |
| --- | --- | --- |
| 0 | Checkpoint `1eeb04a`; added SciPy and Altair bounds to `requirements.txt`; regenerated `requirements.lock.txt` | Done, verified import of SciPy 1.17.1 |
| 1 | `data_io.py`, `column_inference.py`, `cleaning.py` | Done; robust import, inference, consent-driven preview |
| 2 | `statistics_core.py`, `fitting_core.py` | Done; five model families, weighting, diagnostics |
| 3 | `visualization_core.py` | Done; ten chart types, HTML + PNG, explicit warnings |
| 4 | `domain_modules.py`, `result_schema.py`, generalized `ask_muse.py` sections | Done; optional domain layers, one result schema, 10-section registry |
| 5 | `general_app.py`, `data/examples/` (4 synthetic datasets) | Done; Streamlit steps A-G, sample workflow preserved in `app.py` |
| 6 | `analyze_dataset.py`, exports, 10 new test modules | Done; CLI + ZIP/CSV/JSON/MD/HTML/PNG exports |
| 7 | README, docs, CI, `.gitignore`, `results/README.md` | Done; this report |

The original `app.py`, `analysis_core.py`, `analyze_experiment.py` and their
tests were **not replaced**. That keeps the voltage-current sample workflow
working with its original labels, metrics and exports. `general_app.py` and
`analyze_dataset.py` are the new general entry points. Both Streamlit apps
share `ask_muse.py`.

## Measured verification

Commands run from `/home/user/meta_hackathon` with the local `.venv`
(CPython 3.11.2, pandas 3.1.0, numpy 2.4.6, SciPy 1.17.1, Altair 6.3.0,
Streamlit 1.66.1, Matplotlib 3.11.2, pytest 9.1.1):

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | **327 passed, 2 skipped** in 78.04 s (final run on `arena/1f347bab-meta-hackathon`) |
| `.venv/bin/python -m pytest -m "not live" -q` with coverage | 327 passed, 2 deselected |
| Coverage of the nine new deterministic modules + CLI | **91%** (1,338 statements covered of 1,463); per module 87-98% |
| `.venv/bin/ruff check .` | All checks passed |
| `python run_agent_demo.py --case all --strict` | 5/5 cases matched their expected state; 3 audit artifacts per case |
| `.venv/bin/python -m compileall -q *.py` | Exit 0 |
| `python -m streamlit run general_app.py --server.address 0.0.0.0 --server.port 8503` | Uvicorn started on `0.0.0.0:8503`; `/` HTTP 200, `/_stcore/health` HTTP 200, static JS HTTP 200 |
| CLI on sample (`--domain ohmic --unit-x A --unit-y V`) | 16 artifacts written; slope 4.99091, R² 0.999803, candidate resistance 4.99091 ohm |
| CLI on calibration example with `--uncertainty abs_sigma` | Weighted fit enabled; slope 0.0817171 |
| CLI on messy cp1252/semicolon example | cp1252 detected, 8 rows retained, invalid rows excluded from fit but kept in cleaned CSV |
| GitHub Actions CI on PR #2 | `gh pr checks 2 --watch` → **4/4 jobs passed** (Ubuntu + Windows x Python 3.11 + 3.12); lint, offline tests with coverage, byte-compilation |
| GitHub Actions CI on PR #3 (agent) | `gh pr checks 3 --watch` → **4/4 jobs passed** at commit `71a406b`; the first run failed 2/4 on Windows only (see below) |

The two skipped tests are the opt-in live Muse Spark tests in `test_muse.py`.
No `BASETEN_API_KEY` was set in this environment. Provider behaviour was
tested only with a fake OpenAI-compatible client; the live Baseten endpoint
remains **unverified**. `pytest -m live` is available when a key is configured.

Coverage command used:

```bash
.venv/bin/python -m pytest -m "not live" -q \
  --cov=data_io --cov=column_inference --cov=cleaning \
  --cov=statistics_core --cov=fitting_core --cov=visualization_core \
  --cov=domain_modules --cov=result_schema --cov=analyze_dataset \
  --cov-report=term
```

Per-module coverage: `column_inference.py` 98%, `cleaning.py` 97%,
`statistics_core.py` 97%, `domain_modules.py` 95%, `fitting_core.py` 91%,
`result_schema.py` 91%, `data_io.py` 90%, `analyze_dataset.py` 88%,
`visualization_core.py` 87%.

## Acceptance criteria - honest assessment

| Criterion | Status |
| --- | --- |
| App starts | Verified: HTTP 200 for `general_app.py`; AppTest runs both scripts without exceptions. |
| Original sample workflow works | Verified: all legacy tests unchanged and passing; `general_app.py` also reproduces slope 4.99091 / R² 0.999803. |
| Different-column CSV can be uploaded | Verified by `tests/test_general_app.py::test_different_column_csv_upload_and_role_change`. |
| Different X/Y can be chosen | Verified: role widgets tested on an unrelated dataset. |
| Numeric columns inferred without hardcoded names | Verified: `tests/test_column_inference.py` uses arbitrary names. |
| Plots and statistics work | Verified: all ten chart types produce HTML and PNG; statistics tested on known values. |
| Linear fitting works | Verified; plus four other model families. |
| Invalid inputs clear | Verified: import errors, constant X, invalid candidates, ragged rows, bad uncertainty columns produce explicit messages, no tracebacks. |
| AI uses computed results | Verified by a stubbed-provider test asserting the context contains the fitted slope. Offline only. |
| App works without AI | Verified: no-key AppTest shows the warning and all three downloads remain. |
| Exports match current config | Verified: CLI tests compare `results.json` to the returned result; UI shows the Markdown preview for the current configuration. |
| Existing tests pass | Verified: 112 original tests still pass; 117 new tests added. |
| No secrets | Verified by inspection; no key was written to any file. `.env` remains gitignored. |
| Accurate docs | This report and README state measured counts and limitations. |
| No false claim of universal support | README lists supported and unsupported formats/analyses. |

## Known limitations and open items

1. **Live Muse Spark integration is unverified.** No key was available. The
   adapter follows Meta's documented conventions and is covered by offline
   fake-client tests, but a real request/response has not been exercised here.
2. **Decimal comma is not supported.** `1,5` is reported as invalid text, not
   silently converted. Locale-aware parsing is future work.
3. **Interactive HTML plots need internet** to load Vega-Lite from jsDelivr.
   Offline PNG exports use Matplotlib and always work.
4. **Two Streamlit entry points.** The original `app.py` was kept intact to
   preserve its behaviour and tests; `general_app.py` is the general platform.
   A future single-app multipage navigation would require migrating the legacy
   AppTest suite.
5. **Nonlinear fits are heuristic.** `curve_fit` starting guesses are derived
   from the data, but a poor guess or a badly scaled X column can still fail;
   failures are surfaced as structured reasons rather than hidden.
6. **No multivariate, mixed-effects, or time-series-specific models.** Model
   comparison uses AIC on the same observations but is not a substitute for
   residual analysis or domain knowledge.
7. **Uncertainty semantics are user-supplied.** The app assumes the selected
   column is 1-sigma; it cannot distinguish SD, SEM or instrument accuracy.
8. **Coverage of the new modules is 91%, not 100%.** Uncovered branches are
   mostly defensive error paths and rarely selected plot branches.
9. **Large data.** 200,000-row import and 50,000-row plotting caps are
   enforced; larger datasets must be aggregated before upload.
10. **Synthetic examples are illustrative only.** They must never be cited as
    experimental evidence.


---

# Addendum: bounded analysis agent (branch `arena/1f347bab-meta-hackathon`)

## What was added

| File | Purpose |
| --- | --- |
| `agent_tools.py` | Ten-tool closed registry, declarative parameter validation, bounded dispatch, `ToolContext`/`ToolResult`. |
| `agent_planner.py` | Muse Spark plan prompt + strict `validate_plan`, `deterministic_plan` offline fallback, plan hash, numeric grounding check, optional grounded interpretation. |
| `agent_diagnostics.py` | Deterministic `PASS`/`POOR_FIT`/`FAILED`/`INSUFFICIENT` verdicts, residual sign-runs test, quality gate, alternative selection. |
| `agent_audit.py` | `AgentRun` with JSON / JSONL / Markdown / Mermaid exports, evidence refs, per-event actor labels. |
| `agent_core.py` | `AnalysisOrchestrator` bounded state machine. |
| `run_agent_demo.py` | Five reproducible synthetic cases, `--strict`, actor-labelled console trace. |
| `data/agent_examples/` | Five clearly synthetic CSVs with known properties. |
| `general_app.py` step H | Opt-in agent UI: consent checkbox, audit table, Mermaid timeline; audit files added to the export ZIP. |
| `analyze_dataset.py --agent` | CLI writes `agent/` audit artifacts next to the standard exports. |
| `docs/AGENT_WORKFLOW.md`, `docs/TOOL_REGISTRY.md` | Diagram, registry, bounds, verification matrix. |
| 8 new test files | 98 new tests (agent + encoding fallback). |

## Verification (measured)

| Check | Result |
| --- | --- |
| `python -m pytest -q` | **327 passed, 2 skipped** |
| New agent + encoding tests | **98 passed** (8 files) |
| `python run_agent_demo.py --case all --strict` | exit 0; A `DONE` (0 retries), B `DONE` (1 retry -> polynomial), B' `INSUFFICIENT_EVIDENCE`, C `DONE` (9 rows retained / 6 pairs), C' `NEEDS_CLARIFICATION` (0 fits) |
| `ruff check .` | All checks passed |
| AppTest on `general_app.py` | no exceptions; existing 1-button / 3-download contract intact; agent consent path renders audit metrics |
| `analyze_dataset.py --agent` | writes `agent/agent_audit.json`, `agent_events.jsonl`, `agent_report.md` plus standard artifacts |

Behaviours proven by tests (not just claimed): two different validated plans
produce different executed tool sequences; a rejected plan never executes any
of its tools and falls back; `halt_and_explain` suppresses retries;
`max_retries=0` suppresses retries; the global deadline halts cleanly;
destructive tools are rejected without consent; AI prose containing a number
absent from tool outputs is rejected and the deterministic conclusion is kept;
agent fit parameters equal a direct `fit_model` call.

## Honest deviations from the earlier design proposal

1. Case B' (constant response) halts immediately with `INSUFFICIENT_EVIDENCE`
   rather than consuming all three fit attempts: R2 is undefined, so no
   alternative model can be justified. This is the scientifically correct
   choice; the proposal's "retries == 2" expectation was revised.
2. Per-tool timeout uses a shared `ThreadPoolExecutor`; a timed-out tool is
   abandoned (result discarded) rather than forcibly killed, because pure
   NumPy work cannot be interrupted portably on Windows. Documented in
   `docs/AGENT_WORKFLOW.md`.
3. Final interpretation is always deterministic and grounded; Muse Spark
   sections are optional additions that must pass the numeric grounding check.
   This avoids ever presenting an LLM number as a computed result.

## Still unverified

- A **live** Muse Spark plan controlling a real run: no `BASETEN_API_KEY` was
  configured, so the plan path was exercised with a fake OpenAI-compatible
  client and an injected `plan_provider` seam. The two `live` tests remain
  skipped.
- Real-model reliability at producing the strict plan JSON on the first
  attempt, and provider latency. These must be measured with a key; do not
  present estimates as benchmarks.

## Encoding fixture fix

The earlier two-test failure was caused by a snapshot re-encoding the checked-in
cp1252 example (`0xB0` -> UTF-8 `EF BF BD`). The shipped example is now valid
UTF-8; all encoding-fallback assertions generate cp1252/latin-1 bytes in memory
at test time (`tests/test_encoding_fallback.py`, plus the two modified tests).
No tracked file now depends on non-UTF-8 bytes.


## CI incident on PR #3 (fixed)

The first PR #3 run passed both Linux jobs but failed both Windows jobs at the
"Offline tests" step. Remote log archives were unreachable from this sandbox
(`blob.core.windows.net` is outside the allowed hosts), so CI was changed to
write `junit.xml` and emit per-failure `::error::` annotations, and the local
tests were reviewed for platform sensitivity.

Root cause: `test_global_deadline_halts_cleanly` used `max_wall_s=0`, relying on
`time.monotonic()` advancing between two consecutive calls. Linux has
nanosecond resolution; Windows `time.monotonic()` resolves at ~15 ms, so the
deadline could appear unexpired and the assertion failed. Fixed by using
`max_wall_s=-1` (deadline already in the past), which is deterministic on both
platforms. After the fix, `gh pr checks 3 --watch` reported all four matrix
jobs passing. The annotation step remains in CI as a permanent diagnostic aid.

---

## Master-prompt phase (27 Oct 2026) — measured delta

Baseline on this branch: 327 passed, 2 skipped; 5/5 agent demo states; ruff and
compileall clean. After implementation:

```text
.venv/bin/ruff check .                    -> All checks passed
.venv/bin/python -m compileall -q -x '\.venv|\.git' .  -> exit 0
.venv/bin/python -m pytest -q             -> 348 passed, 2 skipped in ~70 s
.venv/bin/python -m pytest -m live -q     -> 2 skipped, 348 deselected
.venv/bin/python -B run_agent_demo.py --case all --strict
                                         -> 7/7 OK (A, B, B', C, C', D, E)
CLI --ai-mock --report-profile scientific
                                         -> slope 4.99091, R² 0.9998029591946405,
                                            labelled mock in report.md/results.json
```

New tests: `tests/test_master_prompt_features.py` (14), two new agent-tool
tests, two new CLI tests, one new AppTest mock-button test, plus updated
demo/orchestrator/registry assertions. New behaviour: scientific report
profile, computed evidence IDs, offline mock, provider status, bounded
transient retries, agent research-question clarification, three allowlisted
tools and reproducible demos D/E.

GitHub Actions PR #4: all four matrix jobs passed (Ubuntu/Windows x Python
3.11/3.12) after this phase, verified with `gh pr checks 4 --watch`.

Still unverified: real Baseten reachability and a genuinely Muse-proposed plan
driving a live agent run. No `BASETEN_API_KEY` was configured in this sandbox;
the two live tests remain skipped. Do not claim live integration in the pitch.


---

## Live-demo hardening phase (27 Oct 2026) — measured delta

Baseline on this branch: 348 passed, 2 skipped. A fake local `.env` reproduced
the six historical failures (4 UI missing-key + 2 live network). Root cause:
import-time `load_dotenv` in three modules mutated `os.environ`.

After the fix:

```text
ruff check .                              -> All checks passed
compileall                               -> exit 0
pytest -q                                -> 426 passed, 2 skipped in 103.66 s
pytest -q with fake .env present          -> 426 passed, 2 skipped
pytest -m live -q                        -> 2 skipped, 426 deselected
pytest --run-live -m live -q (no key)    -> 2 skipped
run_agent_demo.py --case all --strict    -> 7/7 OK
coverage (12 core modules)               -> 92% (2,130/2,305)
Streamlit HTTP smoke                     -> 200 / 200
```

New modules/tests: `provider_config.py`, `tests/conftest.py`, five new test
files, synthetic demo dataset and `docs/LIVE_DEMO_GUIDE.md`. Live Baseten
remains unverified without a real key. See `docs/HARDENING_REPORT.md`.


## CI verification after hardening

PR #5 ran `.github/workflows/ci.yml`; `gh pr checks 5 --watch` reported all
four matrix jobs passing (Ubuntu/Windows x Python 3.11/3.12). This verifies
lint and the offline test suite on both operating systems, not live Muse Spark
access.
