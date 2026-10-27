# LabLens AI — live-demo hardening report

Date: 27 Oct 2026. Branch: `arena/10a318e1-meta-hackathon`.
Baseline commit: `6169aa8` (merge of PR #4). This report records only commands
actually executed in this workspace. `.env` was absent; a **fake** `.env` was
created temporarily to reproduce the developer-machine failures and removed
afterwards. No real credential was read, printed, committed or transmitted.

## 1. Architecture summary

- **Primary app:** `general_app.py` (Streamlit steps A–G plus opt-in bounded
  agent, step H). **Legacy app:** `app.py` with `analysis_core.py`.
- **Headless entry points:** `analyze_dataset.py` (general CLI),
  `analyze_experiment.py` (legacy CLI), `run_agent_demo.py` (A–E demo).
- **Deterministic core:** `data_io.py`, `column_inference.py`, `cleaning.py`,
  `statistics_core.py`, `fitting_core.py`, `visualization_core.py`,
  `domain_modules.py`, `result_schema.py`.
- **Optional AI boundary:** `provider_config.py` (new) owns key/model/endpoint
  configuration; `ask_muse.py` owns request construction, strict report
  validation, bounded retries and the explicitly labelled offline MOCK.
- **Bounded agent:** `agent_tools.py` (13-tool allowlist),
  `agent_planner.py`, `agent_diagnostics.py`, `agent_audit.py`,
  `agent_core.py`. No model-generated code is executed.
- **Exports:** one v2.0 result schema drives cleaned CSV, statistics/fit CSVs,
  strict JSON, Markdown report, plots and a ZIP bundle.

## 2. Ranked issue list found during audit

| Severity | Issue | Evidence | Resolution |
| --- | --- | --- | --- |
| Critical | Import-time `load_dotenv` in three modules repopulated `BASETEN_API_KEY` after tests deleted it | Fake `.env` reproduced 4 failing UI/missing-key tests and 2 live tests attempting network calls | New `provider_config.py`; no `os.environ` mutation; `LABLENS_DISABLE_DOTENV=1` in tests |
| Critical | Live tests were not explicitly opt-in; a key in `.env` made ordinary `pytest` call Baseten | `test_muse.py` failed with `APIConnectionError` / `RuntimeError` under fake `.env` | `--run-live` flag + skip marker; placeholder/missing key skip; network-unreachable skip |
| High | Duplicate/contradictory config and `max_retries=1` could duplicate paid requests | `ask_muse.py`, `agent_planner.py`, app modules read env separately | Centralized config; SDK `max_retries=0`; only bounded local retries remain |
| High | 403 always described as permissions; timeouts were generic network errors | `describe_provider_status(403)` had one message | `describe_provider_error()` inspects safe provider codes; timeout-aware `_network_error()` |
| High | Streamlit reruns/repeated clicks could trigger duplicate AI calls | No guard in either app | Context-bound existing report + session in-flight flag in both apps |
| High | `export_bundle` accepted arbitrary chart names; CLI/ZIP used them as paths | No validation on `charts` keys | `safe_archive_name()` used by `export_bundle`, CLI writer and ZIP writer |
| Medium | Very large finite values produced `success=True` with NaN/inf fit/statistics | Synthetic `y≈1e308` regression | `fit_linear`/`fit_model` return structured failure; `describe_numeric` marks summary invalid; CI/degenerate interval fixed |
| Medium | Missing/blank/placeholder keys all looked similar | `.env.example` placeholder could be treated as configured | `api_key_status()` distinguishes missing / placeholder / configured; status message is explicit |
| Medium | Unsupported extensions were not rejected by the reader | `read_csv_robust` accepted any `source_name` | `.csv`, `.tsv`, `.txt` suffix validation (empty suffix remains backward compatible) |
| Medium | First-time UX and AI status were thin | Sidebar only showed configured/not configured | Quick-start expander, explicit `AI status: not run / running / succeeded / failed`, provider status detail |

## 3. Root cause of the six historical failures

With a fake local `.env` present, the baseline suite reproduced exactly this
pattern:

```text
FAILED tests/test_general_app.py::test_provider_status_is_shown_when_no_key
FAILED tests/test_general_app.py::test_no_key_ai_warns_and_still_exports
FAILED tests/test_streamlit_app.py::test_ai_button_without_key_warns_and_never_contacts_provider
FAILED tests/test_streamlit_app.py::test_sidebar_reports_provider_configuration_state
FAILED test_muse.py::test_muse_spark_connectivity
FAILED test_muse.py::test_muse_spark_structured_report
```

The four UI tests use `monkeypatch.delenv("BASETEN_API_KEY")`, but AppTest then
executes `general_app.py` / `app.py`, which called `load_dotenv(ROOT/".env")` at
import time. python-dotenv wrote the developer key back into `os.environ`, so
the UI believed a key was configured and the "never contacts provider" test
failed. The two live tests are in root `test_muse.py` (current equivalent of
the historical `tests/test_muse.py` names); they saw the same repopulated key,
did not require an explicit opt-in, and attempted real HTTPS calls. In this
sandbox the provider is unreachable, so they failed with connection errors.

After the fix, the same fake `.env` reproduction yields:

```text
5 passed, 2 skipped   # targeted six; live tests skip without --run-live
419 passed, 2 skipped # full offline suite with fake .env present
```

## 4. Files modified and why

**New**

- `provider_config.py` — single secret-free configuration source; process env
  wins; `dotenv_values` (no `os.environ` mutation); placeholder detection;
  `LABLENS_DISABLE_DOTENV`; `secret_values()` / `redact()`.
- `tests/conftest.py` — global env isolation + `--run-live` opt-in.
- `tests/test_provider_hardening.py` — 24 mocked provider/config/rerun tests.
- `tests/test_input_validation_hardening.py` — 18 ingestion/safety tests.
- `tests/test_export_safety.py` — 20 export/ZIP/path/consistency tests.
- `tests/test_scientific_regressions.py` — 7 known-value/overflow tests.
- `tests/test_demo_dataset.py` — 2 synthetic demo contract tests.
- `data/demo/linear_calibration_demo.csv`, `data/demo/README.md` — reproducible
  synthetic dataset and explicit "not experimental" description.
- `docs/LIVE_DEMO_GUIDE.md` — setup, PowerShell commands, 2–3 minute script,
  expected outputs, troubleshooting.
- `docs/HARDENING_REPORT.md` — this report.

**Modified**

- `ask_muse.py` — uses `provider_config`; new `describe_provider_error()`;
  timeout-aware network errors; accurate `provider_status()` with `key_state`;
  missing/blank/placeholder error; SDK `max_retries=0`.
- `app.py`, `general_app.py` — removed import-time `load_dotenv`; centralized
  key checks/redaction; duplicate-call guards; AI status captions; first-time
  quick start in `general_app.py`; safe ZIP names.
- `agent_core.py`, `agent_planner.py`, `analyze_dataset.py`,
  `run_agent_demo.py` — centralized key lookup; planner SDK `max_retries=0`.
- `result_schema.py` — `safe_archive_name()` and safe export names; Markdown
  keeps AI/mock separation (existing behaviour retained).
- `data_io.py` — supported-suffix validation.
- `fitting_core.py`, `statistics_core.py` — non-finite overflow regression fix.
- `test_muse.py` — truly opt-in live tests; uses `provider_config`; skips on
  missing/placeholder key or unreachable network.
- `pytest.ini`, `tests/test_ask_muse_provider.py` — live marker description and
  updated SDK retry expectation.
- `.env.example`, `README.md`, `docs/ARCHITECTURE.md`,
  `docs/PROVIDER_INTEGRATION.md`, `docs/AGENT_WORKFLOW.md`,
  `docs/GENERAL_PLATFORM.md`, `docs/SCIENTIFIC_VALIDATION.md`,
  `docs/DEMO_SCRIPT.md`, `docs/EVALUATION_PLAN.md`,
  `docs/IMPLEMENTATION_REPORT.md`, `docs/PROJECT_AUDIT.md`,
  `docs/HACKATHON_CHECKLIST.md`, `docs/HACKATHON_PITCH.md` — configuration,
  commands, counts and honest live status.

## 5. New tests added

| File | Tests | Covers |
| --- | ---: | --- |
| `tests/test_provider_hardening.py` | 24 | successful/missing/blank/placeholder key, 401/403/429, timeout, network, empty/invalid/unexpected response, AI disabled, duplicate UI clicks in both apps, agent consent on rerun, dotenv isolation |
| `tests/test_input_validation_hardening.py` | 18 | empty/whitespace/header-only, unsupported extensions, ragged rows, encodings, duplicate headers/rows, mixed/NaN/inf, huge values, insufficient rows, missing numeric columns, size/row limits, no code execution, traversal-like source names |
| `tests/test_export_safety.py` | 20 | safe archive names, unsafe chart/CLI/ZIP paths, JSON/CSV/Markdown/ZIP consistency, secret-free exports, formula injection, AI vs mock headings |
| `tests/test_scientific_regressions.py` | 7 | known synthetic line, residuals/JSON finiteness, 1e308 overflow, zero variance, non-finite exclusion, non-positive weights, fixed-seed reproducibility |
| `tests/test_demo_dataset.py` | 2 | synthetic README wording, known CLI slope/intercept/R² and labelled mock |
| `tests/conftest.py` | n/a | autouse env isolation + `--run-live` collection skip |

## 6. Exact commands executed and observed results

```text
# Baseline (clean sandbox, .env absent)
.venv/bin/ruff check .                                  -> All checks passed
.venv/bin/python -m compileall -q -x '\.venv|\.git' .  -> exit 0
.venv/bin/python -m pytest -q                         -> 348 passed, 2 skipped in 73.94 s

# Reproduction with a FAKE local .env (removed afterwards)
pytest -q -m 'not live' <4 UI tests + missing-key test> -> 4 failed, 1 passed
pytest -q test_muse.py                                  -> 2 failed (provider unreachable)

# After fixes, with the same FAKE .env present
pytest -q <same 6 historical equivalents>               -> 5 passed, 2 skipped
.venv/bin/python -m pytest -q                          -> 419 passed, 2 skipped in 84.65 s

# Final clean-sandbox verification
.venv/bin/ruff check .                                  -> All checks passed
.venv/bin/python -m compileall -q -x '\.venv|\.git' .  -> exit 0
.venv/bin/python -m pytest -q                          -> 419 passed, 2 skipped in 86.06 s
.venv/bin/python -m pytest -m live -q                  -> 2 skipped, 419 deselected
.venv/bin/python -m pytest --run-live -m live -q       -> 2 skipped (no usable key)
BASETEN_API_KEY=your_baseten_api_key_here pytest --run-live -m live -q
                                                       -> 2 skipped (placeholder)
.venv/bin/python -B run_agent_demo.py --case all --strict
                                                       -> 7/7 OK (A, B, B', C, C', D, E)
.venv/bin/python -B analyze_dataset.py data/sample_voltage_current.csv --x current_A --y voltage_V --output-dir /tmp/final_cli_sample
    -> slope 4.99091, intercept 0.00545455, R² 0.9998029591946405, 16 files
.venv/bin/python -B analyze_dataset.py data/demo/linear_calibration_demo.csv --x time_s --y signal_mV --model linear --output-dir /tmp/final_cli_demo --ai-mock --report-profile scientific --question "How does signal_mV vary with time_s?"
    -> slope 2.5, intercept 0.1, R² 1.0, 12 observations, 16 files, labelled OFFLINE MOCK
.venv/bin/python -m pytest -q --cov=provider_config --cov=ask_muse --cov=result_schema --cov=data_io --cov=fitting_core --cov=statistics_core --cov=agent_core --cov=agent_planner --cov=agent_tools --cov=agent_diagnostics --cov=agent_audit --cov=run_agent_demo
    -> 92% (2,103/2,276 statements), 419 passed, 2 skipped
HTTP smoke on 0.0.0.0:8503: / -> 200, /_stcore/health -> 200,
    preview Origin header -> 200
```

Installed versions: Python 3.11.2, Streamlit 1.66.1, pandas 3.1.0,
numpy 2.4.6, SciPy 1.17.1, Altair 6.3.0, matplotlib 3.11.2, openai 3.40.0,
pytest 9.1.1, ruff 0.17.3.

## 7. Scientific validation and limits

- Known synthetic line `y = 2.5x + 0.1` is recovered by both `fit_linear` and
  legacy `analyze_linear`; residuals sum to zero; JSON has no NaN/Infinity.
- Large-offset OLS, weighted fits, polynomial/exponential/log/power recovery,
  row-permutation invariance and R²/RMSE definitions remain covered by existing
  tests; all pass.
- New regression: finite `y≈1e308` no longer yields `success=True` with NaN.
  `fit_linear`/`fit_model` return a structured non-finite failure;
  `describe_numeric` marks the summary invalid and omits overflowed mean/std/CI;
  legacy `analyze_linear` raises a clear ValueError.
- Zero variance, constant response, insufficient rows, non-finite pairs and
  non-positive weights produce explicit outcomes, not invented numbers.
- Limits: this is not universal scientific validity. Support remains bounded
  delimited numeric data, selected model families, stated assumptions and
  user-supplied units. No causal inference or calibrated instrument uncertainty
  is inferred.

## 8. Security issues found and resolved

- **Secret handling:** no `.env` is tracked; `git ls-files` lists only
  `.env.example`. No import-time env mutation. Process env always wins.
  `provider_config.secret_values()` / `redact()` remove both process-env and
  local-file values from UI errors. No real key was written or printed.
- **Test isolation:** `LABLENS_DISABLE_DOTENV=1` in an autouse fixture prevents
  a developer `.env` from turning unit tests into live calls.
- **Live-call control:** live tests require `--run-live` **and** a usable key;
  ordinary CI never calls Baseten. SDK retries disabled; local retries bounded.
- **Error leakage:** raw exception text is never surfaced for network errors;
  provider body codes are mapped to short safe hints only.
- **Archive safety:** `safe_archive_name()` rejects absolute paths, drive
  letters, parent traversal, backslashes, empty components and control chars;
  used by `export_bundle`, CLI file writes and ZIP writes.
- **Code execution:** static tests assert ingestion/cleaning/agent modules do
  not contain `eval`, `exec`, `compile`, `subprocess`, `os.system` or
  `__import__`. Uploaded formula-like cells are preserved as text and escaped
  on CSV export.
- **Credential action needed:** if the fake-looking key from earlier chat was
  ever real, rotate it out-of-band. This project did not rotate or revoke any
  credential.

## 9. Remaining known bugs and external blockers

| Item | Status | Note |
| --- | --- | --- |
| Live Muse Spark reachability / quota / real response | **BLOCKED** | No real `BASETEN_API_KEY` and Baseten is outside this sandbox's allowed hosts. Live tests skip; do not claim verified. |
| Real AI-proposed plan driving a live agent run | **BLOCKED** | Same credential/network dependency. Offline plan and simulated outage are verified. |
| Demo video recording | **NOT RUN** | `docs/LIVE_DEMO_GUIDE.md` is ready; recording and portal length/visibility checks are human steps. |
| CI on this branch | **NOT RUN** | Local lint/tests/compile/app smoke pass; GitHub Actions for this branch should be checked after push. |
| Arbitrary scientific formats / causal inference | Out of scope | Documented limitation, not a bug. |

## 10. Local run steps (Windows PowerShell)

```powershell
cd F:\meta-hacathon\meta_hackathon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q -x '\.venv|\.git' .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run general_app.py
```

Optional live key: `Copy-Item .env.example .env`, then edit `.env` locally.
Never commit, print or screen-share it. Live test command:

```powershell
.\.venv\Scripts\python.exe -m pytest --run-live -m live -v
```

## 11. Final hackathon demonstration

Use `docs/LIVE_DEMO_GUIDE.md` and `data/demo/linear_calibration_demo.csv`.
The 2–3 minute sequence shows upload → cleaning → computed fit → labelled
offline MOCK → CSV/JSON/ZIP exports → offline test result. If a real key works,
press the separate live AI button once and label the output "AI-generated,
unverified". If the provider fails, local results and downloads remain intact.

## 12. Readiness decision

**READY FOR DEMO** for the deterministic offline workflow, exports, bounded
agent audit trail and explicitly labelled OFFLINE MOCK. Live Muse Spark
end-to-end remains **BLOCKED** until a real key and network access are
available; the demo must say that honestly rather than presenting a mock as a
live AI response.
