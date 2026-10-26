# Scientific validation

## Mathematical definitions

For paired retained observations `(Iᵢ, Vᵢ)`, LabLens fits `Vᵢ = mIᵢ + b + εᵢ` by unweighted least squares. It returns fitted values `mIᵢ+b`, residuals `Vᵢ - fittedᵢ`, `R² = 1 - SSres/SStot`, and `RMSE = sqrt(SSres/n)`. R² is reported as undefined when `SStot=0`; a slope is rejected when current does not vary. The slope has resistance units only when voltage and current units are respectively V and A.

## Test methodology

Offline unit tests check exact and noisy fits, lengths, minimum observations, nonfinite values, constant current and voltage, order invariance, scaling/offset behavior, alias detection, cleaning counts and row correspondence, explorer predictions, output structure, and repeatability. `test_muse.py` is an optional live integration test and can incur network/provider usage; it is skipped when no key is configured. Routine local validation should not set the key.

Run `python -m pytest -v`. Tests must use isolated values and temporary output directories. The CLI supports `--output-dir` to avoid replacing project artifacts during validation.

## Residual and uncertainty limits

Residual plots can expose visible patterns but cannot establish independence, normality, or constant variance. No confidence intervals, parameter standard errors, instrument uncertainty, calibration corrections, weighting, or systematic-error model are supplied. Outliers are never removed automatically. High R² does not establish causal or physical correctness.

## Reproducibility

Download the JSON record and cleaned CSV together. The record states the selected columns and units, source hash, cleaning policy and counts, model, metrics, timestamp, provenance caveat, and AI provider/model status. Rerun with the original CSV and chosen columns in the dashboard or CLI (CLI alias selection must be unambiguous). The hash identifies the uploaded bytes; it does not verify provenance.

## Known limitations

The current app fits a straight line only and treats x and y values as exact for OLS. Provenance and units are user supplied or unknown. AI claims are not calibrated probabilities, and numerical claims in generated interpretation require user review against the deterministic record.
