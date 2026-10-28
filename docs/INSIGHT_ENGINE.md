# Deterministic key insights

`insight_engine.discover_insights(result)` reads the existing version 2.0 result. `build_result` generates an additive `insights` block, so Streamlit, the general CLI, `results.json`, Markdown and ZIP share the same cards. The app renders the cards after roles and fitting are configured and before the detailed Explore section. No network request or raw-row transmission is involved. The block is not automatically sent in the provider context.

Each card has an identifier, fixed priority, directly computed observation, separate interpretation, result-field evidence paths, limitations, suggested investigation and reason for highlighting. The paths reference the same stored result; fit parameters and statistics remain authoritative. Markdown escapes untrusted input. No card asserts a physical theory, causal mechanism, or calibrated confidence.

## Rules and limits

A maximum of five cards are sorted by a fixed priority: excluded invalid pairs, user-selected duplicate removal, limited/saturated sample, IQR outlier flags, linear fit parameters, fit diagnostics, then source/fit coverage. This is a transparent presentation rule, **not** a statistical or scientific-importance score. It does not currently rank by the research question, effect size, robustness, external evidence or calculated power. More urgent cards can displace lower-priority ones. Fewer cards appear when criteria are not satisfied.

- The sample warning appears for fewer than four fitted observations or nonpositive residual degrees of freedom. Four is a presentation heuristic, not a guarantee of adequate power or independent observations.
- IQR flags are heuristic; they do not prove bad measurements and do not remove rows. A duplicated row can be a valid replicate.
- A linear-parameter card requires a successful linear fit, at least four observations and finite slope and intercept. It uses the selected unit strings, which may be missing or unverified.
- An in-sample diagnostic card additionally requires finite R² and RMSE and positive residual degrees of freedom. R² is not evidence of causality or model validity, and RMSE is not instrument precision. No in-sample metric identifies a scientific law.
- Coverage is a count, not a count of independent replicates. Missing or unusable inputs suppress unsupported cards.

The existing app provides column profiles, data-quality previews, statistics, correlations, plots, fit comparisons and conditional Ohmic theory separately. It does not currently discover change points, group differences or time-dependent patterns as insight cards, or infer a theory automatically. Sampling, apparatus, calibration, and physical meaning require independent context. Review all findings and unit hints before interpreting or exporting them.

## Unit provenance

For historical compatibility the UI may prefill `A`/`V` from current/voltage column names. If a value matches such a hint the app warns and records `matches_unverified_header_hint`; a different nonblank UI value is recorded as `selected_or_retained`, and blank as `unspecified`. The UI can retain prior widget values, so the record does not assert that a value was freshly entered. A matching value may also have been typed by a user, so this conservative label does **not** prove how it was entered or imply confirmation. Users must verify and correct units. The CLI records nonblank explicit units as `user_entered`. Origin fields and units are included in JSON and Markdown.

## Tests

`python -m pytest -q tests/test_insight_engine.py tests/test_general_app.py tests/test_result_schema.py tests/test_analyze_dataset.py tests/test_theory_engine.py` tests known synthetic fits, rank ordering, missingness/duplicates, outlier flags, small and failed fits, constants/nonfinite values, unsupported models, escaping, provider-context exclusion, the bundled sample, UI and unit correction. The numerical examples validate software behavior, not the scientific provenance of the sample.
