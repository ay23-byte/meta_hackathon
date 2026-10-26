# LabLens AI architecture

## Data flow

```text
CSV upload or bundled sample (bounded: 5 MiB / 200,000 rows)
  → pandas CSV reader with explicit parse errors
  → alias suggestion + user-confirmed x/y columns and units (sanitized)
  → analysis_core.prepare_analysis_data
  → analysis_core.analyze_linear (centred OLS)
  → metrics, fitted/residual plots, hypothetical explorer
  → optional user-triggered Muse Spark interpretation
  → strict schema validation + context-hash binding
  → in-memory Markdown / cleaned CSV / JSON downloads
```

`app.py` is the Streamlit dashboard; `analyze_experiment.py` is a headless
CLI; both call the same pure functions in `analysis_core.py`.
`ask_muse.py` owns the only AI provider boundary and the only AI report
schema. `tests/` uses pytest plus Streamlit's AppTest runner.

## Numerical analysis

`analysis_core.py` owns alias detection, paired-row numeric cleaning, line
fitting, hypothetical candidate predictions, and deterministic export
serialization. Cleaning converts selected columns positionally (so a
non-default DataFrame index cannot mis-pair rows), retains source row
numbers and order, and excludes only rows with missing, nonnumeric, NaN, or
infinite selected values. Duplicate column names in a DataFrame are
rejected rather than silently dropped; `pandas.read_csv` mangles duplicate
CSV headers before they reach the core.

The fit solves `V = mI + b` with **centred normal equations**:
`m = Σ(x-x̄)(y-ȳ) / Σ(x-x̄)²`, `b = ȳ - m·x̄`. This is the same OLS line
as `np.polyfit`, but avoids catastrophic cancellation when measurements
have a large offset and small spread. Non-finite results, overflow, and
insufficient spread raise `ValueError` instead of returning a misleading
line. `R² = 1 - SSres/SStot` is `None` when `SStot = 0`; RMSE uses
denominator n. No uncertainty estimate, weighting, or outlier rule is
inferred. See `docs/SCIENTIFIC_VALIDATION.md`.

## AI integration

`ask_muse.py` is imported only when needed and is called only after an
explicit dashboard button press. It sends a bounded compact summary
(question, dataset filename and row counts, selected column names and
sanitized units, computed metrics, residual summary, limitations, and
candidate predictions) to the configured Baseten OpenAI-compatible
endpoint for Muse Spark Open. It never transmits raw rows or credentials.
The key is read from the environment/`.env`, never logged.

Requests use a `developer` instruction message, JSON mode when supported,
`max_completion_tokens`, and the provider's default sampling, with one
bounded HTTP-400 compatibility fallback. Responses must be a single valid
JSON object matching `ask_muse.validate_report`: eight required sections
(each once), ≤25 words per section, ≤2 claims, all six evidence fields,
and hard character limits. The validator returns a **sanitized** structure,
discarding unexpected provider keys. Malformed JSON is rejected — it is
never displayed as model text and never treated as structured evidence.
`reasoning_content` is never substituted for the report.
`app.validate_ai_report()` delegates to the same validator, so there is one
schema, not two.

A SHA-256 hash of the full displayed context (including the provider model)
binds a cached report to the current analysis; changing the data, question,
unit, explorer input, or model invalidates it. AI content is rendered as
plain text so model output cannot inject links or markup. See
`docs/PROVIDER_INTEGRATION.md` for the full contract and verification
status.

## Export workflow

The dashboard provides in-memory Markdown, cleaned CSV, and JSON downloads;
opening the page never rewrites project artifacts. The record includes UTC
time, source filename and SHA-256 of the original bytes, selected columns,
units, row counts, cleaning policy, model and method, metrics, warnings,
software versions, provenance status, and whether AI was used (plus the
sanitized interpretation when present). Unit strings are sanitized to
prevent spreadsheet formula injection in CSV headers; untrusted text is
escaped in the Markdown report. The CLI writes the same deterministic
numbers plus PNG plots to a chosen output directory; its generated files
are gitignored (see `results/README.md`).

## Error handling

CSV parse/size/row errors, invalid column choices, too few valid pairs,
non-varying x values, invalid explorer values, oversized or malformed
provider responses, truncated or empty output, missing API keys, and
provider/network failures all receive user-facing feedback. Local analysis
and exports never depend on API availability. Errors are bounded,
secret-free, and never include raw provider exception text.
