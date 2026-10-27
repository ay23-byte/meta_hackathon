# Evaluation plan

This plan separates **measured results** from **proposed future work**.
Measured results below were produced in this repository on 26 Oct 2026;
nothing is extrapolated into a user study or a performance benchmark.

## Numerical correctness — executed

- Independent `np.linalg.lstsq` oracle agrees with `analyze_linear` to
  ~1e-12 relative on noisy data.
- Residual identity, R² and RMSE definitions, order invariance, affine
  rescaling, negative slopes, constant current/voltage, non-finite inputs,
  and extreme magnitudes are covered by tests.
- Large-offset regression (`x ≈ 1e9`) now returns intercept 2.0 rather
  than the −79 produced by an uncentred fit.
- Sample dataset is pinned at 11 rows, slope ≈ 4.990909, intercept
  ≈ 0.005455, R² ≈ 0.999803, RMSE ≈ 0.022156.
- CLI and dashboard call the same core; CLI artifacts are checked against
  the core result, the input SHA-256, and the residual identity.

## AI claim grounding — executed offline

- `tests/test_ask_muse_provider.py` uses a fake OpenAI-compatible client
  (never a live call): request parameters, JSON/fenced JSON parsing,
  canonicalization, sanitization, size limits, empty/malformed/oversized/
  truncated output, reasoning-only output, HTTP error mapping, the single
  HTTP-400 compatibility fallback, network errors, and missing keys.
- `tests/test_streamlit_app.py` uses Streamlit AppTest: valid report
  rendering, invalid report rejection, provider failure display,
  secret redaction, and context-hash invalidation.
- `app.validate_ai_report` and `ask_muse.validate_report` are the same
  schema by construction (the former delegates to the latter).

## Failure modes and reproducibility — executed

- AppTest uploads cover empty CSV, invalid UTF-8, too few valid pairs,
  constant current, same-column selection, constant voltage, 200,001 rows,
  a >5 MiB file, and malformed/non-finite explorer input.
- Export JSON is parsed strictly (`allow_nan=False`); cleaned CSV rows and
  residuals match the deterministic analysis; CLI output goes to `tmp_path`.
- Source hashes are deterministic for identical input bytes and change with
  the input; the AI context hash also binds to results and provider model.

## Measured quality gates

| Gate | Command | Result |
| --- | --- | --- |
| Offline tests | `python -m pytest -q` | 112 passed, 2 skipped |
| Coverage | `pytest --cov=analysis_core --cov=ask_muse --cov=app --cov=analyze_experiment -q` | 98% statements (615 total, 12 uncovered) |
| Lint | `ruff check .` | clean |
| Compile | `python -m compileall -q ...` | clean |
| Live provider | `python -m pytest -m live -v` | **not run** — no `BASETEN_API_KEY` in this environment |

## Proposed (not yet done)

- With a real key: run the live suite and record whether the strict
  eight-section report is produced on the first attempt, how often a retry
  or fallback occurs, and the observed latency. Do not present these as
  benchmarks until measured.
- With real users: a small task-based study comparing LabLens against a
  spreadsheet/script workflow using a predefined checklist (valid rows,
  selected variables, model equation, parameters, residual review,
  limitations, reproducibility). Record task completion and errors from
  observed sessions only.
- With domain data: validate weighted fits and calibrated uncertainty against
  a known measurement model before claiming calibrated errors. The general
  engine now supports weighted fitting, but the *meaning* of a supplied
  uncertainty column (SD vs SEM vs accuracy) still requires human input.
- Independent review of AI claims against the numerical record is still a
  human step; do not claim automated verification.

## General platform - measured gates (27 Oct 2026)

These results were measured after the Phase 0-7 implementation. The original
sample-workflow gates above remain valid for `app.py`.

| Gate | Command | Result |
| --- | --- | --- |
| Offline tests | `python -m pytest -q` | 327 passed, 2 skipped (98 new agent/encoding tests) |
| New-module coverage | `pytest -m "not live" -q --cov=data_io ... --cov=analyze_dataset` | 91% statements (1,338/1,463); per module 87-98% |
| Lint | `ruff check .` | clean |
| Compile | `python -m compileall -q *.py` | clean |
| UI smoke | `streamlit run general_app.py` on `0.0.0.0:8503` | `/` and `/_stcore/health` HTTP 200 |
| AppTest for both apps | `pytest tests/test_general_app.py tests/test_streamlit_app.py -q` | pass, no exceptions |
| Live provider | `python -m pytest -m live -v` | **not run** - no `BASETEN_API_KEY` |

Verified numerically on synthetic data with known parameters: linear
slope/intercept (including `x ~ 1e9`), polynomial coefficients in original
units, exponential rate, logarithmic and power parameters, weighted-fit
improvement, exponential doubling time, Pearson/Spearman correlations,
Student-t CI, and IQR flags. See `tests/test_fitting_core.py` and
`tests/test_statistics_core.py`.


## Bounded analysis agent - measured gates (27 Oct 2026)

| Gate | Command | Result |
| --- | --- | --- |
| Full offline suite | `python -m pytest -q` | 327 passed, 2 skipped |
| Agent unit + orchestrator tests | `pytest tests/test_agent_*.py tests/test_encoding_fallback.py -q` | 98 passed |
| Agent-module coverage | `pytest -m "not live" --cov=agent_* --cov=run_agent_demo` | 90% (806/899 statements; per module 83-98%) |
| Five-case demo | `python run_agent_demo.py --case all --strict` | exit 0; all 5 observed states matched |
| AI plan influence | `tests/test_agent_orchestrator.py::test_two_different_valid_ai_plans_produce_different_tool_sequences` | pass - different tool sequences and plan hashes |
| Plan rejection | `tests/test_agent_orchestrator.py::test_rejected_ai_plan_never_executes_its_tools` | pass - fallback used, unknown tool never dispatched |
| Grounding | `tests/test_agent_planner.py::test_grounding_check_rejects_invented_numbers` | pass - fabricated 42.123 rejected |
| Bounds/consent | deadline, retry-budget, destructive-consent tests | pass |
| Live Muse-proposed plan | `pytest -m live -v` | **not run** - no `BASETEN_API_KEY` |

See `docs/AGENT_WORKFLOW.md` for the full verification matrix and the explicit
list of implemented-but-live-unverified behaviours.

---

## Master-prompt phase — measured gates (27 Oct 2026)

| Gate | Command | Result |
| --- | --- | --- |
| Full offline suite | `pytest -q` | **348 passed, 2 skipped in ~70 s** |
| Live-marker selection | `pytest -m live -q` | 2 skipped, 348 deselected (no key) |
| Lint / byte-compile | `ruff check .`, `compileall` | clean / exit 0 |
| Seven-case A-E demo | `python -B run_agent_demo.py --case all --strict` | 7/7 expected states OK |
| New master-prompt tests | `pytest tests/test_master_prompt_features.py -q` | 14 passed |
| Core-module coverage | `pytest -q --cov=ask_muse --cov=result_schema --cov=agent_* --cov=run_agent_demo` | 92% (1,441/1,574 statements) |
| New agent tools | `pytest tests/test_agent_tools.py -k "compare_models or time_series"` | 2 passed |
| CLI offline mock | `analyze_dataset.py ... --ai-mock --report-profile scientific` | labelled mock in `report.md` and `results.json`; slope 4.99091, R² 0.9998029591946405 |
| AppTest mock button | `pytest tests/test_general_app.py -k offline_mock` | 1 passed; provider client never constructed |
| Live provider | `pytest -m live -v` | **not run** — no `BASETEN_API_KEY` |

The two skips are opt-in live tests, not hidden failures. No benchmark, latency
or real-model reliability number is claimed.
