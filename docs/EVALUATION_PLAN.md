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
- With domain data: extend to weighted fits and calibrated uncertainty —
  only after the measurement model and instrument uncertainty are known.
- Independent review of AI claims against the numerical record is still a
  human step; do not claim automated verification.
