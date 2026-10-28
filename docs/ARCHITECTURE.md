# LabLens AI architecture

## General platform (added 27 Oct 2026)

The general-purpose path uses `general_app.py` (Streamlit, steps A-G) and
`analyze_dataset.py` (headless CLI). Its modules are pure and independently
testable:

```text
data_io → column_inference → cleaning → (user roles/consent)
        → statistics_core + fitting_core + domain_modules
        + visualization_core → result_schema (v2.0)
        → ai_context → ask_muse (optional) → export_bundle
```

The legacy path below (`app.py`, `analyze_experiment.py`,
`analysis_core.py`) is preserved unchanged. Both paths share `ask_muse.py`
as the single AI provider boundary. See `docs/GENERAL_PLATFORM.md` for the
full module map, the result schema and the anti-misleading chart rules.

## Original sample workflow

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

---

## Master-prompt architecture update (27 Oct 2026)

The legacy data flow above is preserved. The general platform now has these
additional boundaries:

```text
result_schema.evidence_index(result)  -> bounded ID -> computed-values map
result_schema.ai_context(result, research_question)
    -> { ..., research_question, result_ids, evidence_index }
ask_muse.build_prompt(..., profile=legacy|scientific)
    -> strict JSON schema; when result_ids exist, every claim needs evidence_ids
ask_muse.generate_interpretation(...)
    -> live-provider wrapper ONLY; bounded 408/429/5xx retries; never a mock
ask_muse.generate_mock_report(...)
    -> offline_mock wrapper; deterministic templates; strict validation
result_schema.markdown_report / export_bundle
    -> separate heading and disclaimer for AI vs OFFLINE MOCK
```

`ask_muse.REPORT_PROFILES` owns two independent registries. `legacy` keeps the
original eight titles and ten-title registry for backward compatibility;
`scientific` adds the research-question/method/fit/next-step report. Both use
one `validate_report()` implementation. `allowed_evidence_ids` makes the schema
stricter when computed IDs are supplied: each claim must carry 1-4 IDs from
that set, with no duplicates, unexpected characters or invented values. Extra
provider keys are always dropped.

`provider_status()` performs **no network call**. It reports whether a key is
configured, whether a local `.env` exists, and that `live_call_attempted` and
`live_verified` are false. The UI shows it in the sidebar and step F. Live
requests use one bounded conservative-shape fallback on HTTP 400 and at most
`MAX_TRANSIENT_RETRIES` additional attempts for 408/429/5xx or transport
errors; 4xx configuration errors are never retried. The SDK's own
the OpenAI client now uses `max_retries=0`; only the adapter's bounded local retries remain.

The offline mock is a separate code path: `MOCK_MODEL_ID =
"offline-deterministic-mock"`, `source="offline_mock"`, `is_mock=True`, and a
disclaimer beginning "OFFLINE MOCK REPORT ... NOT AI". It reads only computed
context values and passes the same strict validator. `report.md`, `results.json`
and the UI label it as a mock; it can never be mistaken for a live response.

The bounded agent now starts at a **question gate** before `inspect_dataset`.
`normalize_question()` records an explicit default when the user supplies none;
`clarify_question()` stops with `NEEDS_CLARIFICATION` and three dataset-specific
options when the question is vague. The question is included in the Muse plan
prompt, the AI interpretation digest, and the JSON/Markdown audit trail. The
tool allowlist has 13 entries (see `docs/TOOL_REGISTRY.md`), including model
comparison, evidence summary and descriptive time-series summary. No
model-generated source code is executed.


---

## Hardening update (27 Oct 2026)

`provider_config.py` is now the only configuration boundary: it reads `.env`
with `dotenv_values` (no `os.environ` mutation), gives process environment
variables precedence, detects placeholder keys and provides `redact()`.
`ask_muse.py`, both Streamlit apps, the CLI, the agent core, the planner and the
demo driver all import it; no module calls `load_dotenv` at import time.

`result_schema.safe_archive_name()` validates every export file name before
`export_bundle()`, `analyze_dataset.py` and `general_app.py` write files or ZIP
entries. This blocks absolute paths, drive letters, `..`, backslashes, empty
components and control characters.

Both Streamlit apps now keep a context-bound validated AI report plus an
in-flight session flag, so a rerun or repeated button press cannot duplicate a
provider request. Step F/H captions report `not run`, `running`, `succeeded` or
`failed`; the bounded agent still requires its own consent checkbox.


## Report state (provenance fix, 28 Oct 2026)

Step F stores one context-bound state
`{"hash", "live", "mock", "active"}` in `st.session_state["ai_state"]` and a
separate `ai_context_hash`. Live and mock wrappers are both preserved for the
same analysis, but only the active one is displayed and exported. A live action
reuses only `state["live"]`; the mock action reuses only `state["mock"]`.
`ask_muse.report_kind()` / `enforce_report_provenance()` are the single source
of truth for the `source`, `is_mock` and `provider_status` markers. The legacy
`app.py` has a smaller `stored_live_report()` guard that rejects a stored mock
but still reuses older wrappers without provenance fields.
