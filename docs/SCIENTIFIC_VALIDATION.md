# Scientific validation

## General engine definitions (added 27 Oct 2026)

The general platform (`statistics_core.py`, `fitting_core.py`) uses these
definitions. They were verified against synthetic data with known parameters.

- Sample variance/SD use `ddof=1`; population values use `ddof=0`.
- The 95% CI for the mean is a two-sided Student-t interval with `n-1`
  degrees of freedom. It assumes independent, approximately normal
  observations and is **not** an instrument-accuracy interval.
- Pearson and Spearman coefficients are computed on pairwise-complete finite
  observations; a constant column makes correlation undefined (reported as
  `null` with a reason). p-values come from SciPy and assume independence.
- IQR fences `Q1 - 1.5*IQR`, `Q3 + 1.5*IQR` only *flag* candidate outliers.
- Linear fitting solves weighted centred normal equations in
  `fitting_core.fit_linear`; polynomial fitting solves a scaled Vandermonde
  system and composes coefficients back into the original X units.
- Nonlinear models use `scipy.optimize.curve_fit` with `sigma = 1/sqrt(w)`
  when inverse-variance weights are supplied. Non-convergence returns a
  structured reason, never a partial result.
- `R² = 1 - SSres/SStot` is `null` when `SStot = 0`; adjusted R², reduced
  chi² and AIC require a positive residual degree of freedom.
- AIC comparison is only meaningful for fits on the same observations with
  the same weighting. Model suggestions are linearised-correlation
  heuristics, not model selection.

Tests in `tests/test_statistics_core.py` and `tests/test_fitting_core.py`
assert exact recovery on synthetic data (linear slope/intercept including
`x ~ 1e9`, polynomial coefficients, exponential rate, log and power
parameters), weighted-fit behaviour, structured failures and extrapolation
flags.

## Original sample workflow

## Mathematical definitions

For paired retained observations `(Iᵢ, Vᵢ)`, LabLens fits
`Vᵢ = mIᵢ + b + εᵢ` by unweighted ordinary least squares using centred
normal equations:

```
m = Σ(Iᵢ - Ī)(Vᵢ - V̄) / Σ(Iᵢ - Ī)²
b = V̄ - m·Ī
fittedᵢ = m·Iᵢ + b
residualᵢ = Vᵢ - fittedᵢ
R²  = 1 - SSres/SStot          (None when SStot = 0)
RMSE = sqrt(SSres / n)         (denominator n, not n-2)
```

`R²` is reported as **undefined** (`None`) when voltage has no variance; a
slope is rejected when current does not vary. The slope has resistance
units only when voltage and current units are respectively V and A.
Overflow, non-finite coefficients, and insufficient numerical spread raise
an error rather than returning a misleading line.

Why centred: an uncentred design matrix loses precision when x has a large
offset relative to its spread. A regression test uses
`x = [1e9, 1e9+1, 1e9+2, 1e9+3]`, `y = 5x + 2`; `np.polyfit` returns an
intercept near −79 on this input, while the centred solution returns 2.0
to machine precision. Both are OLS mathematically, but only one is
numerically reliable.

## Test methodology and actual results

Verified offline in this environment (26 Oct 2026):

- `python -m pytest -q` → **112 passed, 2 skipped**. The two skips are the
  opt-in live Muse Spark tests (`test_muse.py`, marker `live`), which need
  `BASETEN_API_KEY`.
- `pytest --cov=analysis_core --cov=ask_muse --cov=app
  --cov=analyze_experiment` → **98% statement coverage** (615 statements,
  12 uncovered, all defensive branches).
- `ruff check .` → clean.
- Streamlit AppTest executes the real app script: sample render, upload
  errors, size/row limits, data-quality warnings, explorer edge cases,
  no-key AI path, valid/invalid AI reports, and provider failures.

Numerical tests cover exact and noisy fits against an independent
`np.linalg.lstsq` oracle, residual identity, R²/RMSE definitions, order
invariance, affine rescaling, negative slopes, large offsets, extreme
magnitudes, constant current/voltage, non-finite inputs, duplicate
columns, non-default indices, and the published sample-dataset numbers.
Provider tests use a fake client; they do **not** establish that the live
endpoint works.

Run offline validation with:

```bash
python -m pytest -m "not live" -q
ruff check .
```

Live validation (billable, opt-in):

```bash
python -m pytest -m live -v
```

Tests use isolated values and `tmp_path` output directories. The CLI
supports `--output-dir` so validation never overwrites tracked artifacts.

## Residual and uncertainty limits

Residual plots can expose visible patterns but cannot establish
independence, normality, or constant variance. No confidence intervals,
parameter standard errors, instrument uncertainty, calibration
corrections, weighting, or systematic-error model are supplied. Outliers
are never removed automatically. High R² does not establish causal or
physical correctness. The measurement explorer returns hypothetical model
predictions with an explicit extrapolation flag — never observations and
never uncertainty intervals.

AI-generated text is untrusted: it is size-limited, schema-validated,
sanitized, displayed as plain text, and labeled as not independently
verified. Numerical claims in an AI report must be checked against the
deterministic record by a human.

## Reproducibility

Download the JSON record and cleaned CSV together. The record states the
selected columns and units, source SHA-256, cleaning policy and counts,
model and method, metrics, timestamp, software versions, warnings,
provenance caveat, and AI provider/model status. Rerun with the original
CSV and chosen columns in the dashboard or CLI (CLI alias selection must be
unambiguous). The hash identifies the uploaded bytes; it does not verify
provenance. `requirements.lock.txt` records the exact tested environment.

## Known limitations

The current app fits a straight line only and treats x and y values as
exact for OLS. Provenance and units are user supplied or unknown. The
bundled sample dataset has no independently verified origin. Live Muse
Spark end-to-end behaviour has not been verified in this environment;
see `docs/PROVIDER_INTEGRATION.md`.

---

## Master-prompt validation additions (27 Oct 2026)

All numbers below come from tests actually executed on this branch; synthetic
datasets are labelled as such and are not experimental evidence.

- **Evidence IDs.** `result_schema.evidence_index()` produces bounded,
  ASCII-safe IDs (`dataset.source`, `cleaning.summary`, `corr.pearson`,
  `fit.linear`, `compare.*`, `stat.*`, `outliers.summary`) mapped to computed
  values. `ai_context()` keeps `result_ids` and `evidence_index` consistent
  even when trimming to `max_chars`; a 4,000-character context test passes.
  `ask_muse.validate_report(..., allowed_evidence_ids=...)` rejects missing,
  unknown, duplicate, oversized and malformed IDs.
- **Offline mock grounding.** `generate_mock_report()` quotes only values from
  the supplied computed context. On the bundled sample, the mock reports
  slope 4.99091, intercept 0.00545455, R² 0.999803, RMSE 0.0221565 and n=11 —
  exactly the CLI's deterministic outputs. It is labelled NOT AI in
  `results.json`, `report.md` and the UI.
- **Model comparison tool.** On `y = 2x + 1` (10 synthetic points),
  `compare_models(["linear", "polynomial"])` returns two successful rows with
  R² ≈ 1.0 and `n_observations == 10`; an unknown model is rejected before
  execution.
- **Evidence summary tool.** After one fit, `evidence_summary()` returns one
  result ID, `n_fits == 1`, and `n_valid_pairs == 10`.
- **Time-series summary tool.** On `y = 2x + 1` with `x = 0..9`,
  `time_series_summary(max_lag=2)` returns `n_points == 10`, `mean_step == 2.0`,
  lag-1 Pearson correlation ≈ 1.0, and a note disclaiming forecasting. `max_lag=9`
  is rejected by the parameter bound.
- **Bounded retries.** A fake provider returning HTTP 503 three times produces
  exactly `MAX_TRANSIENT_RETRIES + 1 == 3` local attempts, then a safe error;
  HTTP 401 produces one attempt; one 503 followed by a valid report succeeds in
  two attempts.
- **Full offline suite.** `pytest -q` → **419 passed, 2 skipped**; the two
  skips are the opt-in live Muse Spark tests. `pytest -m live -q` → 2 skipped,
  419 deselected. No live scientific claim is made.


---

## Hardening update (27 Oct 2026)

New regression: finite responses near `1e308` previously produced
`fit_linear(..., success=True)` with NaN slope/intercept and `describe_numeric`
with infinite mean/variance. `fit_linear` and `fit_model` now return a
structured non-finite failure; `describe_numeric` marks the summary invalid,
omits overflowed dispersion values and keeps finite min/max/quantiles;
`confidence_interval_mean` returns `interval=None` for a non-finite standard
error instead of a degenerate interval. Floating-point warnings are suppressed
locally with `np.errstate`. Known-value and fixed-seed synthetic tests pass.
Final full offline suite: **419 passed, 2 skipped**.
