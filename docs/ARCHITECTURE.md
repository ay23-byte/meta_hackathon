# LabLens AI architecture

## Data flow

```text
CSV upload or bundled sample
  → pandas CSV reader
  → alias suggestion + user-confirmed x/y columns and units
  → analysis_core.prepare_analysis_data
  → analysis_core.analyze_linear
  → metrics, fitted/residual plots, explorer, and downloads
  → optional user-triggered Muse Spark interpretation
```

## Numerical analysis

`analysis_core.py` owns alias detection, paired-row numeric cleaning, line fitting, and hypothetical candidate predictions. The app and `analyze_experiment.py` call the same core. Cleaning retains row order and source row numbers. Rows are omitted only when a selected pair is missing, nonnumeric, or nonfinite. The fit is ordinary least squares for `V = mI + b`; RMSE uses denominator n. R² is undefined when voltage has no variance. No uncertainty estimate or outlier rule is inferred.

## AI integration

`ask_muse.py` lazily runs only after an explicit dashboard button press. It sends the research question, dataset filename and row counts, selected column names and units, computed metrics, residual summary, and limitations to the configured Baseten OpenAI-compatible endpoint with Muse Spark Open. It does not transmit raw rows or credentials. Output is validated as JSON sections and evidence-linked claims; malformed JSON falls back to model text and is not treated as structured evidence. Numerical calculations remain authoritative in Python.

## Export workflow

The dashboard provides in-memory Markdown, cleaned CSV, and JSON downloads; opening the page does not rewrite project artifacts. The record includes UTC time, source filename and SHA-256, selected columns, units, row counts, cleaning policy, model, metrics, limitations, provenance status, and whether AI was used. The CLI can optionally save these plus plots to a chosen output directory.

## Error handling

CSV parse errors, invalid column choices, too few valid pairs, non-varying x values, invalid explorer values, missing API keys, provider failures, empty responses, and malformed report structure receive user-facing feedback. Local analysis and exports do not depend on API availability.
