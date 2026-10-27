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
| `.venv/bin/python -m pytest -q` | **229 passed, 2 skipped** in 72.41 s (final run) |
| `.venv/bin/python -m pytest -m "not live" -q` with coverage | 229 passed, 2 deselected |
| Coverage of the nine new deterministic modules + CLI | **91%** (1,338 statements covered of 1,463); per module 87-98% |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/python -m compileall -q *.py` | Exit 0 |
| `python -m streamlit run general_app.py --server.address 0.0.0.0 --server.port 8503` | Uvicorn started on `0.0.0.0:8503`; `/` HTTP 200, `/_stcore/health` HTTP 200, static JS HTTP 200 |
| CLI on sample (`--domain ohmic --unit-x A --unit-y V`) | 16 artifacts written; slope 4.99091, R² 0.999803, candidate resistance 4.99091 ohm |
| CLI on calibration example with `--uncertainty abs_sigma` | Weighted fit enabled; slope 0.0817171 |
| CLI on messy cp1252/semicolon example | cp1252 detected, 8 rows retained, invalid rows excluded from fit but kept in cleaned CSV |
| GitHub Actions CI on PR #2 | `gh pr checks 2 --watch` → **4/4 jobs passed** (Ubuntu + Windows x Python 3.11 + 3.12); lint, offline tests with coverage, byte-compilation |

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
