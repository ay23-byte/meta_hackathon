# LabLens AI pitch

## One-line pitch

LabLens AI turns experimental CSV measurements into reproducible
calculations, visual diagnostics, and evidence-grounded scientific
interpretation — with limits stated as clearly as the results.

## Problem and impact (Impact, 30%)

Students and researchers move between spreadsheets, scripts, plots, and
written summaries. That makes analysis hard to reproduce and makes it easy
for a conclusion to outpace the measurements. A scientific assistant must
explain results without replacing or inventing them. LabLens targets the
"Push the Frontier" theme: accelerating a scientific experiment while
keeping the evidence trail intact.

Do not claim measured time savings, adoption numbers, or verified
experimental findings — no user study has been run.

## Distinctive workflow

LabLens connects data inspection, confirmed variable selection,
deterministic fitting, residual diagnostics, a hypothetical follow-up
explorer, and a portable record in one short flow. Cleaning is explicit:
excluded pairs are counted, source row numbers are retained, and no
outliers are removed automatically. The JSON and Markdown records carry the input SHA-256, cleaning policy, warnings, and selected runtime software versions; the ZIP includes both records. The standalone cleaned CSV does not contain this provenance.

## Meta AI tooling (Use of Meta AI Tooling, 25%)

On an explicit user action, Muse Spark Open via Baseten interprets a
compact, bounded summary of the computed results and limitations. The raw
data and API key are never sent. The integration follows Meta's documented
conventions — a `developer` instruction message, JSON mode, the provider's
default sampling, a bounded completion budget — and includes one graceful
compatibility fallback for gateways that reject newer parameters.

What goes beyond a basic integration: a single strict report schema shared
by producer and UI; hard size limits and sanitization of all AI output;
evidence-linked claims with six mandatory fields plus computed `evidence_ids`;
two independently validated report profiles; context-hash binding so a report
cannot be attributed to a different dataset; bounded transient retries;
explicit rejection of empty, truncated, or reasoning-only output; and AI text
rendered as plain text with a "not independently verified" label. A separate,
conspicuously labelled deterministic OFFLINE MOCK is available for offline
demos and is never presented as Muse Spark output. The deterministic result
always remains authoritative.

Attribution "Built with Muse Spark Open" appears in the UI, as required by
the Muse Model License.

## Technical depth and execution (20%)

- Numerically stable centred OLS; a regression test catches the large-offset
  intercept failure of an uncentred fit.
- Shared core for dashboard and CLI; headless-safe plotting.
- 426 offline tests passing, 2 live tests skipped without a key, Streamlit
  AppTest UI tests, fake-client provider contract tests, CLI/export artifact
  tests, and seven reproducible A-E agent demo cases.
- Lint-clean (`ruff`), pinned reference environment, and a Linux + Windows
  CI matrix.
- Bounded uploads, CSV formula-injection-safe headers, secret-free errors.

## Demo (25%)

A ~3:00 script (`docs/DEMO_SCRIPT.md`) shows the primary `general_app.py`
workflow, computed metrics and residual diagnostics, a scientific-profile
report, the explicitly labelled OFFLINE MOCK fallback, and all exports. The
terminal shows `run_agent_demo.py --case all --strict` with seven cases,
including an ambiguous question (D) and a simulated provider outage (E).
A no-key fallback is rehearsed so the demo holds up even if the provider is
unavailable. The video must still be recorded and its length confirmed
against the current rules.

## Limitations and roadmap

Current support is delimited CSV/TSV-style numeric data with dot decimals;
the general platform supports weighted fits and five model families, but not
Excel/JSON/binary formats, multivariate regression, automatic domain
detection or causal inference. It does not infer calibrated instrument
uncertainty or independently verify data provenance. Live Muse Spark
end-to-end behaviour still needs a credential in the submission
environment; no key was configured in this sandbox. Claims are now linked to
computed result IDs and checked against the supplied allowlist, but a human
must still verify the scientific interpretation. Next work should add
broader scientific formats and carefully justified uncertainty-aware
designs before making any broader claims.
