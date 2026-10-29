# Offline two-experiment comparison

In the existing general app, select **Compare a second experiment (offline)** after configuring the first analysis. Upload a second delimited file, select its numeric X/Y columns, enter its X/Y units, and confirm that the mapped quantities, units, methods and conditions are comparable. Both first-experiment units must be nonempty. Unit strings must match exactly (case-sensitive after trimming); automatic conversions and dimensional inference are not supported. Header-derived default units on the first file are unverified hints and must be checked. The confirmation is a user assertion, not validation of scientific equivalence. The confirmation resets when either file, mappings, units, or first-dataset cleaning decisions change.

Each dataset retains its own filename, SHA-256, mappings, units, paired row counts and mean values. The first dataset uses the first analysis's cleaning choices; the second uses its imported rows and excludes nonfinite/incomplete pairs only from the comparison. The source frames are not mutated. Each dataset needs at least two finite pairs. The separate means and the descriptive second-minus-first Y mean are computed locally over all valid pairs; the scatter uses at most the first 2,000 pairs per dataset, with a disclosure. A shared X/Y plot is not a fit and does not prove relationships, significance, causation, comparable sampling or shared physical conditions. A mean difference can reflect different X ranges or sampling. No error bars, confidence, normalization, interpolation, aggregation across datasets or inferred instrument precision are supplied.

The current JSON and Markdown in the existing ZIP include the optional comparison summary and provenance when confirmed. They do not include second-dataset raw rows or the comparison plot; the first dataset's existing cleaned-data export is unchanged. Uploaded names and other metadata are exportable and may be sensitive. The comparison is never added to the existing provider context; no external call is made. This is a limited two-dataset feature, not a multi-experiment database, model-comparison or inference system.

Tests: `python -m pytest -q tests/test_experiment_comparison.py tests/test_general_app.py tests/test_result_schema.py tests/test_export_safety.py`. They exercise known paired means, missing values, incompatible/missing units, explicit and fresh consent, bounded plotting, Markdown/JSON provenance and UI behavior.

## Optional separate linear fits

The explicitly selected **Fit separate unweighted lines** action fits each
mapped dataset independently using ordinary least squares. It reports fitted
parameters, R², RMSE, sample sizes, slope difference and (if the first slope is
nonzero) a slope ratio. These are descriptive, not a significance test; the main
fit's model and weights are not reused. An unequal-sample-size warning is
provided. Instrument uncertainty, paired structure, conditions, sampling and
cleaning differences require separate review. The computed summaries are
included in JSON/Markdown and the evidence ledger.
