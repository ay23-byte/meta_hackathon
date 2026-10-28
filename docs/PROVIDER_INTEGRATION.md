# Muse Spark / Baseten integration

This document separates **verified offline behaviour** from **live
behaviour that still needs a credential**. Do not conflate the two in a
demo, a submission, or a report.

## Configuration

| Setting | Source | Default |
| --- | --- | --- |
| `BASETEN_API_KEY` | `provider_config.py`: process environment first, then gitignored `.env` via `dotenv_values` | none — AI disabled |
| `BASETEN_MODEL` | optional environment override | `meta-models/muse-spark-open` |
| Endpoint | fixed in `ask_muse.BASE_URL` | `https://inference.baseten.co/v1` |
| Timeout / retries | fixed | 90 s; SDK retries disabled; adapter allows at most 2 bounded transient retries |
| Report completion budget | `LABLENS_REPORT_MAX_TOKENS`, optional bounded override | 4096 tokens (1024–16384) |

The default model string is the one published in Meta's hosted-provider
table and in Baseten's model library. Some hackathon accounts are assigned a
dated model identifier; if your provider instructions say so, set
`BASETEN_MODEL` in `.env` rather than editing source. Never put a key in
source, screenshots, logs, or exports.

Sources (public documentation, read 26 Oct 2026):

- Baseten, *Muse Spark Open* model library —
  <https://www.baseten.co/library/muse-spark-open/>
- Meta, *Run inference / hosted providers* —
  <https://dev.meta.ai/docs/muse-spark-open/deploy>
- Meta, *Chat completion* protocol reference —
  <https://dev.meta.ai/docs/protocols/chat-completions>
- Meta, *Structured output (JSON mode)* cookbook —
  <https://dev.meta.ai/docs/cookbook/structured-output>
- Meta, *Build with Muse Spark, now available on Meta Model API* —
  <https://dev.meta.ai/resources/blog/build-with-muse-spark>
- Meta, *Muse Spark Open* model card / Muse Model License —
  <https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B>

## Request contract

`ask_muse.generate_interpretation()` builds a bounded prompt from a compact
summary (question, columns, units, row counts, fit metrics, residual
summary, limitations, candidate predictions). It never includes the raw CSV
or the key. The request then follows the conventions Meta documents for
Muse Spark:

- a **`developer`** instruction message (Meta recommends developer over
  system for standing rules), plus one `user` message;
- **no `temperature` override** — Meta states the model is tuned for the
  default 1.0 and that clearer instructions beat lowering temperature;
- `response_format={"type": "json_object"}` (JSON mode) when accepted;
- `max_completion_tokens` so reasoning tokens are budgeted;
- `stream=False`, bounded timeout and retries.

If the gateway rejects any of the newer parameters with HTTP 400, the
adapter retries **once** with the most conservative request shape (no
`response_format`, legacy `max_tokens`). Other HTTP statuses are mapped to
actionable, secret-free messages; raw exception text is never displayed.

The Muse Model License requires products using the model to display
"Built with Muse Spark Open"; the dashboard shows this in the sidebar and
this is recorded here for the submission record.

## Response contract

`ask_muse.validate_report()` is the single authoritative schema. It returns a
**sanitized** dict or `None`:

- exactly the eight `REQUIRED_TITLES`, each once, case-insensitive but
  canonicalized for display; unknown or duplicate titles rejected;
- section content: non-empty, ≤25 words, ≤400 characters;
- ≤2 claims; every claim has all six non-empty evidence fields, each ≤600
  characters;
- raw response ≤64,000 characters; prompt/context also bounded;
- extra provider keys are discarded so untrusted output cannot reach the UI,
  session state, or exports.

`message.reasoning_content` is **never** used as a substitute for the
report. If reasoning consumes the token budget and visible content is empty,
the adapter raises a specific error. Truncated responses
(`finish_reason == "length"`) are reported as truncated rather than as a
generic JSON failure.

`app.validate_ai_report()` delegates to this validator; there is no second
copy of the rules. Reports are bound to a SHA-256 hash of the full displayed
context (including the model identifier) so a changed dataset, question,
unit, explorer input, or model invalidates a cached report.

## Verification status (honest)

**Verified offline in this repository** (no key required):

- `tests/test_ask_muse_provider.py` exercises the adapter against a fake
  OpenAI-compatible client: request parameters, valid and fenced JSON,
  canonicalization, sanitization, empty/malformed/oversized/truncated
  output, reasoning-only output, HTTP 400/401/403/404/429/5xx mapping,
  the single 400 fallback, network errors, missing key, and size limits.
- `tests/test_streamlit_app.py` exercises the real app with AppTest: valid
  reports render as plain text, invalid reports are rejected, provider
  failures are safe, and context changes invalidate cached reports.
- `ruff check .` is clean; the offline suite passes with 98% statement
  coverage of the four application modules.

**Not verified here (requires a real key and network access):**

- that the Baseten endpoint is reachable from the submission environment;
- that `meta-models/muse-spark-open` (or the account's dated variant) is
  enabled on the account and that `response_format` behaves as documented;
- that the model reliably returns the strict eight-section JSON schema.

Run the opt-in live tests deliberately; they make real, billable calls:

```bash
cp .env.example .env          # add your own BASETEN_API_KEY
python -m pytest --run-live -m live -v   # connectivity + structured-report round trip
python -m streamlit run app.py
```

If the live structured-report test fails, the app still works: calculations,
plots, and all three exports remain available. Say so explicitly rather
than presenting a saved or mocked report as a live result.

## General platform additions (27 Oct 2026)

- `ask_muse.REQUIRED_TITLES` is still the eight-title default. A
  `SECTION_REGISTRY` of ten titles plus `resolve_section_titles()` allows the
  UI/CLI to request a different subset. `build_prompt`, `validate_report` and
  `generate_interpretation` accept an optional `section_titles` argument;
  unknown, duplicate, empty or oversized requests are rejected locally before
  any credential check or network call.
- `result_schema.ai_context()` builds the provider context from the single
  result object. It excludes raw data rows, free-form notes and all prior AI
  text, trims verbose blocks progressively, and guarantees a size bound. A
  stubbed-provider test asserts the context contains the fitted slope.
- `general_app.py` binds the AI report to a hash of the deterministic result
  plus the section list, question and provider model; changing any of them
  invalidates the cached report.
- New tests: `tests/test_ask_muse_sections.py`,
  `tests/test_general_app.py` (AI paths),
  `tests/test_result_schema.py` (context grounding), and
  `tests/test_analyze_dataset.py` (optional AI without a key).

The live endpoint is still unverified in this environment: no
`BASETEN_API_KEY` was configured, so the two `live` tests remain skipped and
all provider tests use a fake client.


## Agent plan path (added 27 Oct 2026)

`agent_planner.request_agent_plan()` is a second, independent Muse Spark call
with the same conventions (`developer` role, JSON mode,
`max_completion_tokens`, one HTTP-400 fallback, no `reasoning_content`
substitution). It receives only a data-quality summary and the tool allowlist -
no raw rows - and returns a JSON plan. `validate_plan()` rejects unknown tools,
out-of-range parameters, forbidden tokens and oversized plans before any tool
executes. `PlannerUnavailable` (including a missing key) falls back to
`deterministic_plan()`, so the agent works fully offline.

The optional final interpretation uses `generate_grounded_interpretation()`,
whose context is only the executed tool outputs; `grounding_check()` rejects
any AI number not present in those outputs. Tests use a fake client and an
injected `plan_provider`. **Live Muse-proposed plans remain unverified** in
this environment because no `BASETEN_API_KEY` was configured. See
`docs/AGENT_WORKFLOW.md`.

---

## Master-prompt provider update (27 Oct 2026)

- **Two strict profiles.** `REPORT_PROFILES = {legacy, scientific}`. `legacy`
  keeps `REQUIRED_TITLES` (eight) and the ten-title registry unchanged.
  `scientific` has its own eight-title registry (Research Question, Dataset
  Overview, Analysis Performed, Main Quantitative Findings, Model-Fit
  Assessment, Uncertainty and Limitations, Possible Scientific Interpretation,
  Recommended Next Investigation). Callers opt in with `profile="scientific"`;
  unknown profiles and cross-profile section names are rejected.
- **Evidence-linked claims.** When `ai_context()` supplies `result_ids`, the
  prompt requires `evidence_ids` (1-4) per claim, drawn only from that list.
  `validate_report()` enforces the same constraint locally. IDs are restricted
  to `[A-Za-z0-9_.:-]{1,64}`; extra fields are discarded.
- **Bounded transient retries.** `TRANSIENT_HTTP_STATUSES = {408,429,500,502,503,504}`;
  `MAX_TRANSIENT_RETRIES = 2`; exponential backoff from 0.25 s. Transport
  errors with no HTTP status get the same bound. 400 still triggers the single
  conservative-shape fallback; other 4xx errors fail immediately. Raw exception
  text is never surfaced. The OpenAI client now uses `max_retries=0` to avoid duplicate SDK-level
  requests; only the adapter's bounded local retries remain.
- **Honest status.** `provider_status()` returns `api_key_configured`,
  `key_source`, `env_file_present`, `mode`, `live_call_attempted=False`,
  `live_verified=False`, `offline_mock_available=True` and a message. It makes
  no network call and never includes the key. The Streamlit sidebar and step F
  display it.
- **Explicit offline mock.** `generate_mock_report()` is a separate function
  with `source="offline_mock"`, `is_mock=True`, `model="offline-deterministic-mock"`
  and `MOCK_DISCLAIMER` starting "OFFLINE MOCK REPORT ... NOT AI". It is NOT
  reachable from `generate_interpretation()`; the UI uses a separate button and
  the CLI uses `--ai-mock`. Exports label it in `report.md` and `results.json`.
- **Live status in this workspace.** No `BASETEN_API_KEY` is configured here.
  `pytest -m live -q` skips both live tests. Fake-client tests verify our
  request/response contract, retries and schema, but **do not verify Baseten
  reachability, entitlement, quota or a real Muse Spark response**.


---

## Hardening update (27 Oct 2026, branch `arena/10a318e1-meta-hackathon`)

- **Root cause fixed:** `app.py`, `general_app.py` and `ask_muse.py` previously
  called `load_dotenv()` at import time. A developer `.env` could repopulate
  `BASETEN_API_KEY` after a test deleted it, causing four UI missing-key tests
  to fail and two live tests to attempt real network calls during ordinary
  `pytest`. All three now use `provider_config.py`, which never mutates
  `os.environ`.
- **Precedence:** a real process environment variable always wins over `.env`.
  `LABLENS_DISABLE_DOTENV=1` disables local file fallback for tests/CI.
- **Validation:** missing, blank and obvious placeholder keys are reported as
  `key_state="missing"|"placeholder"` and never trigger a client.
- **Retries:** the OpenAI client now uses `max_retries=0`; only
  `ask_muse._request_with_bounded_retries()` retries transient 408/429/5xx or
  transport errors, at most `MAX_TRANSIENT_RETRIES=2` additional attempts.
  401/403/404/400 fail immediately with actionable messages.
- **403 nuance:** `describe_provider_error()` inspects safe provider body codes
  to distinguish credential rejection, permission denial, model access and
  quota hints. Raw exception text is never returned.
- **Live tests:** root `test_muse.py` requires `pytest --run-live -m live -v`.
  Without `--run-live`, a usable key, or network reachability, the two tests
  skip. `pytest -m live -q` → 2 skipped, 426 deselected in this workspace.
- **Verification:** full offline suite **426 passed, 2 skipped**; same result
  with a fake local `.env` present; `ruff` and `compileall` clean. Live Baseten
  reachability remains **unverified** because no real key is configured here.


---

## Report provenance fix (28 Oct 2026)

`general_app.py` previously reused any current-context report, so an OFFLINE
MOCK blocked the live button. The fix adds explicit provenance helpers in
`ask_muse.py` and separate live/mock session-state slots in `general_app.py`:

| Field | Live report | Offline mock |
| --- | --- | --- |
| `source` | `live_provider` | `offline_mock` |
| `is_mock` | `False` | `True` |
| `provider_status` | `live_response_validated` | `not_called` |

`_current_report("live")` never returns a mock; `_current_report("mock")` never
returns a live response. A failed live request deactivates the visible report
and shows a redacted, actionable error; it does not fall back to mock output.
Changing the analysis hash invalidates both stored reports. The legacy `app.py`
duplicate-request guard also refuses a stored mock while retaining
backward-compatible reuse of provenance-free live wrappers. Seven new regression
tests in `tests/test_report_provenance.py` cover these paths. Full offline
suite: **426 passed, 2 skipped**. Live provider reachability is still
unverified without a real key.

## Audit update (28 Oct 2026)

The general app offers an opt-in, single-request connectivity check in the
sidebar. It sends only `Reply with OK.`, has a 30-second timeout and no
retries; a nonempty response does not validate structured report generation.
It was tested with a fake client only, not a real provider. A separate checkbox
requests live regeneration for the same analysis; validated UI reports include
an analysis fingerprint, validation status and UTC validation time. The
configuration-only sidebar check remains unverified even after another action;
the report/check output shows its own outcome. Before a live interpretation,
review filenames, column names, question and computed summaries for sensitive
information; the context excludes raw rows but is not a privacy guarantee.

## Incomplete live responses — local hardening

`finish_reason=length` is classified as truncation even when visible content
is empty. Reasoning-only output without that finish reason is incomplete, not
a report; private reasoning is never displayed or exported. A refusal is
reported separately. Neither condition triggers an automatic retry. The error
identifies the configured report token limit and suggests fewer sections or an
explicit `LABLENS_REPORT_MAX_TOKENS` adjustment; a larger limit can consume
more credits and may not work on every deployment. It is not evidence that
token exhaustion caused a particular failure. Agent plan requests use their
own budget without mutating the shared report setting. Numeric `Retry-After`
values up to five seconds are honored for transient retries; longer or
unparseable delays stop automatic retry and ask the user to wait.

The reported Baseten failure has not been reproduced against the real provider
in this environment. String final content and the response error paths were
tested with mocked SDK-shaped responses. Other content representations are
not claimed as supported; no reasoning field is used as an answer.
