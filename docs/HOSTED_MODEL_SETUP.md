# Optional user-configured hosted model

The generic hosted mode is separate from Muse Spark/Baseten, NVIDIA NIM, local Llama/Ollama, and the
explicitly labelled offline mock. It defaults to the requested model identifier
`meta-models/Muse-Glimmer-30B`, **not a verified model/provider contract**. No
endpoint is included. Obtain and independently verify the official hackathon
provider's OpenAI-compatible HTTPS base URL, exact model ID, API key, usage
terms, credit balance and whether billing can occur. A default identifier or
configured key is not evidence of access, authenticity or free inference.

The generic hosted mode reads **process environment variables only**; it does not read the
project `.env` file. Do not paste keys into chat, screenshots, source, exports
or logs. Set them privately in the same terminal/process that starts Streamlit.

| Variable | Meaning |
| --- | --- |
| `LABLENS_AI_PROVIDER` | Must explicitly equal `hosted`. |
| `LABLENS_API_KEY` | Provider-issued secret; no default. |
| `LABLENS_BASE_URL` | Confirmed OpenAI-compatible HTTPS base URL; no default. No URL credentials, query or fragment. |
| `LABLENS_MODEL` | Optional confirmed model ID; default `meta-models/Muse-Glimmer-30B`. Explicitly blank is rejected. |
| `LABLENS_MAX_OUTPUT_TOKENS` | Optional integer 128–8192; default 2048. |
| `LABLENS_TIMEOUT_SECONDS` | Optional integer 5–120; default 60 (120 for NVIDIA); write/pool and default read timeout. |
| `LABLENS_CONNECT_TIMEOUT_SECONDS` | Optional integer 1–120; default 10 (30 for NVIDIA). |
| `LABLENS_READ_TIMEOUT_SECONDS` | Optional integer 5–600; default 300 for NVIDIA when `LABLENS_TIMEOUT_SECONDS` is unset, otherwise that setting. Bounds read/stream inactivity, not total elapsed time. |

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

## NVIDIA NIM mode

Select `LABLENS_AI_PROVIDER=nvidia` in the process environment or the project-local `.env`. Configure
`NVIDIA_API_KEY` and the exact `NVIDIA_MODEL` from NVIDIA's catalog in the
process environment or that project `.env`. On Windows, the historical
`F:\meta-hacathon\.env` is used only when the project `.env` does not exist.
Process values (including blank) take precedence; a blank provider fails closed.
When no provider is specified, the legacy Muse Spark path remains the default.
`LABLENS_DISABLE_DOTENV=1`
disables the file fallback. The NVIDIA endpoint is fixed to
`https://integrate.api.nvidia.com/v1`; generic endpoint/model settings are ignored.
The default model is `meta/muse-glimmer-30b`; `NVIDIA_MODEL` may override it,
while an explicitly blank value fails closed. Access and identity remain unverified. Set process
variable `LABLENS_NVIDIA_STREAM=1` for buffered streaming, or `0` (default)
for non-streaming. Both paths retain the same report and evidence checks.
See README for setup and model-list validation.

No NVIDIA live access, model identity or billing has been verified by tests.
The old Bluesminds mode is no longer selectable; an old selection fails closed.
This note preserves migration history without silently changing providers.

### Timeout investigation

`python nvidia_smoke.py --confirm-live` sends a short potentially billable
completion using the configured NVIDIA model and endpoint. Add `--compare-report`
only if you consent to a second, full-report request on bundled synthetic data.
It prints no prompts, results, or keys. Set `LABLENS_NVIDIA_STREAM=1` to test
the streaming path. Neither command runs automatically.

The INFO log `hosted_request` reports stage (model catalog, initial response, or
stream read), prompt character count, token limit, chunks received and time to
first chunk after the streaming response starts. It never logs the prompt or
chunk text. HTTP read timeout measures transport inactivity, not a total
deadline; network heartbeats or fragmented bytes can reset it without producing
an SDK chunk. No log can diagnose an earlier failure that did not emit it.
Inference is never retried automatically. `LABLENS_NVIDIA_CATALOG_RETRIES`
(0–2, default 0) only retries transient failures of the model-list GET with
bounded delay; unsupported or excessive Retry-After values stop retries.
