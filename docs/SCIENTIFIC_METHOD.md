# Scientific method and local AI

1. Upload a bounded CSV/TSV, preview cleaning, and explicitly map variables and
   units. The application does not identify physical experiments from filenames.
2. Python calculates pairwise-valid statistics, chosen fit, residuals and
   metrics. Unweighted linear intervals are conditional on the stated error
   assumptions; measurement, prediction and parameter uncertainties differ.
3. Optional educational templates describe Ohm's law, pendulum, Hooke's law,
   Newton cooling and thermal expansion. They do **not** automatically select
   columns, transform data, infer constants, or validate a physical law.
4. A user-requested local Llama report receives a compact result summary and
   optional question, not intentionally the raw rows. Names and free text may
   still be sensitive. All model-generated text is untrusted interpretation.
5. The existing strict section/claim validator, allowed evidence IDs and limited
   numerical checks reject some invalid outputs. An existing ID does not prove
   a claim is supported; unrecognized numbers, units, citations, causal claims,
   semantic support and scientific interpretation require human review.
6. Export JSON/CSV/Markdown/ZIP and optional PDF with manifest and figures.
   Checksums detect changes but do not establish authenticity or provenance.

The model is `llama3.2:1b` from Meta Llama, served through local Ollama, not
Muse Spark or Muse Glimmer. Its output must not replace calculations or
measurements. See `MATHEMATICS_AND_UNCERTAINTY.md` for method-specific bounds.
