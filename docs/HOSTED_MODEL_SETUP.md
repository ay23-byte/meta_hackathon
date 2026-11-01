# Optional user-configured hosted model

This adapter is separate from Muse Spark/Baseten, local Llama/Ollama, and the
explicitly labelled offline mock. It defaults to the requested model identifier
`meta-models/Muse-Glimmer-30B`, **not a verified model/provider contract**. No
endpoint is included. Obtain and independently verify the official hackathon
provider's OpenAI-compatible HTTPS base URL, exact model ID, API key, usage
terms, credit balance and whether billing can occur. A default identifier or
configured key is not evidence of access, authenticity or free inference.

The adapter reads **process environment variables only**; it does not read the
project `.env` file. Do not paste keys into chat, screenshots, source, exports
or logs. Set them privately in the same terminal/process that starts Streamlit.

| Variable | Meaning |
| --- | --- |
| `LABLENS_AI_PROVIDER` | Must explicitly equal `hosted`. |
| `LABLENS_API_KEY` | Provider-issued secret; no default. |
| `LABLENS_BASE_URL` | Confirmed OpenAI-compatible HTTPS base URL; no default. No URL credentials, query or fragment. |
| `LABLENS_MODEL` | Optional confirmed model ID; default `meta-models/Muse-Glimmer-30B`. Explicitly blank is rejected. |
| `LABLENS_MAX_OUTPUT_TOKENS` | Optional integer 128–8192; default 2048. |
| `LABLENS_TIMEOUT_SECONDS` | Optional integer 5–120; default 60. |

Use your OS's secret-management method to set the key in the process environment;
configure the other values from your provider's instructions. Do not use the
sample placeholders as real settings. Restart Streamlit after changes.

```powershell
# Set the nonsecret fields to the actual confirmed values in your own shell.
$env:LABLENS_AI_PROVIDER = 'hosted'
# Set LABLENS_BASE_URL, LABLENS_MODEL and LABLENS_API_KEY privately as appropriate.
python -m streamlit run general_app.py
```

Under **Hosted model (explicit configuration and consent)**, enable controls.
Review the status and warning. Only after confirming the endpoint, terms and
credit balance yourself, select the consent checkbox and click **Generate hosted
model interpretation**. Regeneration requires another click and can incur a
charge. There are no automatic retries or alternate-provider fallbacks. LabLens
cannot guarantee that a request is free or that the configured endpoint is
legitimate. A successful response is not proof of model identity or billing.

The request includes a compact analysis summary, selected column names, units,
question and optional user-supplied research context. It excludes raw CSV rows
by design, but names and context may be sensitive. The existing report schema,
analysis-bound evidence IDs and limited numeric guard are applied before
storing. Evidence-ID membership is not semantic support; unsupported numbers,
units, citations and scientific interpretations require human review. When
validation fails, deterministic results and exports remain available.

## Verification status

Provider tests use mocked clients and make no external calls. No hosted model
request has been made in this sandbox; endpoint reachability, contract, actual
model identity, credits and report quality are unverified. The configured
model name in provenance is a **requested identifier**, not independent model
verification. If an endpoint supplies a different response model identifier,
the report is rejected rather than mislabelled.

## Bluesminds mode

Set `LABLENS_AI_PROVIDER=bluesminds` and `BLUESMINDS_API_KEY` privately in
the Streamlit process environment. Defaults are `https://api.bluesminds.com/v1`,
`meta/muse-glimmer-30b`, and 512 output tokens. `LABLENS_BASE_URL`,
`LABLENS_MODEL`, `LABLENS_MAX_OUTPUT_TOKENS`, and `LABLENS_TIMEOUT_SECONDS`
can override these. See README for Windows setup and troubleshooting. This
mode sends `reasoning_effort=none`, temperature 0.2, and top_p 1. It never
uses reasoning content as a final answer. No live access is verified.
The explicit connectivity test sends one potentially billable request without
analysis data; consent is required. There are no automatic retries.
