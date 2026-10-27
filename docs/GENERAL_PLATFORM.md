# General platform design

This document describes the general-purpose analysis path added on branch
`arena/e7fb1bbb-meta-hackathon`. The original `app.py` /
`analyze_experiment.py` voltage-current workflow is intentionally untouched so
that its behaviour and tests remain a valid reference.

## Entry points

| Layer | General | Legacy (preserved) |
| --- | --- | --- |
| UI | `general_app.py` | `app.py` |
| CLI | `analyze_dataset.py` | `analyze_experiment.py` |
| Result schema | `result_schema.py` (v2.0) | `analysis_core.serialize_analysis_exports` |

## Module map

```
data_io.py            robust import: decode, sniff, header checks, coercion
column_inference.py   per-column classification + role suggestions
cleaning.py           previewable, consent-driven plan + application
statistics_core.py    descriptive stats, correlation, covariance, CIs, outliers
fitting_core.py       linear / polynomial / exponential / log / power
visualization_core.py 10 Altair chart types + Matplotlib PNG fallback
domain_modules.py     explicit, assumption-bearing interpretation layers
result_schema.py      single result object, Markdown, CSV/JSON/ZIP exports
ask_muse.py           optional Muse Spark adapter + strict report validation
general_app.py        Streamlit steps A-G
analyze_dataset.py    headless CLI using the same modules
```

All deterministic functions are pure (no Streamlit calls), which is why they
are unit-testable without a browser. `general_app.py` only orchestrates them
and uses `st.cache_data` for import, inference and fits.

## Data flow

```
bytes -> read_csv_robust -> DataFrame (dtype=object, raw values preserved)
      -> infer_columns -> profiles -> suggest_roles -> USER OVERRIDES
      -> build_plan -> preview_cleaning -> USER CONSENT -> apply_cleaning
      -> paired_values (finite X/Y) -> fit_model / compare_models
      -> statistics_core + domain_modules + visualization_core
      -> build_result (v2.0) -> ai_context -> (optional) ask_muse
      -> export_bundle -> cleaned CSV, stats CSV, fit CSVs, JSON, MD, HTML, PNG
```

Raw columns are never overwritten. Cleaning adds `__numeric__<column>`
companions containing parsed floats; missing, invalid and infinite cells become
NaN in the companion but stay untouched in the raw column. Invalid rows are
excluded from fitting by pairwise completeness but **remain in the cleaned
CSV**. Exact-duplicate removal is the only row deletion and is opt-in.

## Model details

| Model | Equation | Notes |
| --- | --- | --- |
| `linear` | `y = a*x + b` | Weighted centred normal equations; numerically stable for `x ~ 1e9`. |
| `polynomial` | `y = sum c_k x^k` | Least squares on scaled `(x-mean)/range`, coefficients composed back to original units. Degree 1-6; needs at least degree+2 observations. |
| `exponential` | `y = A*exp(k*x) + C` | SciPy `curve_fit`, bounded `maxfev`, multiple starting guesses derived from data. |
| `logarithmic` | `y = A*ln(x) + C` | Requires all fitted `x > 0`. |
| `power` | `y = A*x^k` | Requires all fitted `x > 0` and `y > 0`. |

Weights are inverse variances `w = 1/sigma^2`; `curve_fit` receives
`sigma = 1/sqrt(w)` with `absolute_sigma=True`. Metrics include R²,
adjusted R², RMSE, MAE, chi², reduced chi² and AIC. Undefined values are
reported as `null` with a reason, never as 0.

`predict_with_flags` labels each prediction `in_range`, `extrapolated` or
`undefined`. `suggest_models` ranks linearised correlations and always returns
a caveat that these are shape heuristics, not model selection.

## Domain layers

`apply_domain()` never inspects a filename. The default `generic` layer
produces no derived physical quantity. `ohmic` reports a *candidate*
resistance in ohms only if the selected model is linear and the user supplies
matching current/voltage units (`A`/`V`, `mA`/`mV`, `µA`/`µV`); otherwise it
reports an unnamed proportionality coefficient. `calibration` reports
sensitivity and an inverse-prediction formula. `growth` converts an
exponential rate into doubling time or half-life. Every derived value is
separated into `computed`, `derived`, `hypotheses` and `warnings`.

## Visualisation choices that avoid misleading the reader

- Dual Y axes are refused: secondary Y columns are plotted separately and a
  warning explains why.
- Line and time-series charts warn when the source X was unsorted and when X
  values repeat.
- Grouped bar charts always start the Y axis at zero and warn that bar height
  is an arithmetic mean with no error bars unless uncertainties were supplied.
- Error bars use the supplied column verbatim; the app never invents or
  rescales uncertainties and asks the user to verify SD vs SEM vs accuracy.
- Histograms state the bin count; density plots state that bandwidth affects
  shape; box plots state that whiskers are min-max and outliers are retained.
- Correlation heatmaps leave undefined pairs blank and state that correlation
  is not causation.
- Residual plots require a successful fit and show a zero reference line.

Interactive HTML uses Altair/Vega-Lite loaded from jsDelivr; offline PNG
export uses Matplotlib, so PNGs always work.

## Result schema v2.0

`build_result()` returns one dictionary with `schema_version`, UTC timestamp,
`source` (name, SHA-256, encoding, delimiter, warnings), `roles`, `cleaning`,
`statistics`, `correlation`, `outliers`, `fit`, `model_comparison`,
`model_suggestions`, `domain`, `visualizations`, `notes`, `warnings` and
`ai`. `json_safe()` removes NumPy scalars and non-finite floats so
`json.dumps(..., allow_nan=False)` always succeeds.

`ai_context()` derives a compact, deterministic-only context from that object:
it excludes raw data rows, prior AI text and free-form notes, progressively
trims verbose blocks, and guarantees a size bound. `markdown_report()` writes
ten numbered sections; section 10 attributes AI prose to the provider and
labels it unverified when present. `export_bundle()` produces the file map
consumed by both the ZIP download and the CLI.

## AI report validation

`ask_muse.REQUIRED_TITLES` remains the eight-title default for backward
compatibility. `SECTION_REGISTRY` adds two optional sections (Data Quality and
Cleaning, Alternative Explanations) for a maximum of ten.
`resolve_section_titles()` rejects unknown, duplicate, empty and oversized
requests. `validate_report()` requires exactly the requested titles, rejects
unexpected/duplicate names, enforces content/word/character limits, drops
extra keys, and validates all six claim fields. `generate_interpretation()`
validates local configuration before touching credentials and never substitutes
`reasoning_content` for a structured report.

## What is deliberately out of scope

See the "Supported scope and honest limitations" section of `README.md`. The
platform does not claim universal file-format support or universal scientific
analysis. It supports bounded delimited-text import, a defined set of
statistics/plots/models and explicitly selected interpretation layers.

---

## Master-prompt platform update (27 Oct 2026)

`ai_context()` now accepts `research_question` and emits bounded `result_ids`
plus an `evidence_index` map from `result_schema.evidence_index()`. The ID list
and map stay consistent while the context is trimmed to `max_chars`. Step F in
`general_app.py` offers a profile selector (`legacy` / `scientific`), a live
Muse Spark button, and a **separate** deterministic OFFLINE MOCK button. The
sidebar and step F show `ask_muse.provider_status()`, which never claims live
verification. `markdown_report()` section 10 now has distinct headings and
disclaimers for AI-generated text and a mock, and prints computed result IDs
for claims. The CLI exposes the same capabilities through `--question`,
`--report-profile`, `--ai-mock` and `--agent-question`.
