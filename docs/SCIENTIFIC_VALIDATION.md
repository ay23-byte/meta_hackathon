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
