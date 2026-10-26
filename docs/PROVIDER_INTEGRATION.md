# Muse Spark / Baseten integration

This document separates **verified offline behaviour** from **live
behaviour that still needs a credential**. Do not conflate the two in a
demo, a submission, or a report.

## Configuration

| Setting | Source | Default |
| --- | --- | --- |
| `BASETEN_API_KEY` | local `.env` (gitignored) or environment | none — AI disabled |
| `BASETEN_MODEL` | optional environment override | `meta-models/muse-spark-open` |
| Endpoint | fixed in `ask_muse.BASE_URL` | `https://inference.baseten.co/v1` |
| Timeout / retries | fixed | 90 s, at most 1 SDK retry |
| Completion budget | `MAX_COMPLETION_TOKENS` | 4096 tokens |

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
python -m pytest -m live -v   # connectivity + structured-report round trip
python -m streamlit run app.py
```

If the live structured-report test fails, the app still works: calculations,
plots, and all three exports remain available. Say so explicitly rather
than presenting a saved or mocked report as a live result.
