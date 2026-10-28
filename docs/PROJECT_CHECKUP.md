# Project checkup — 28 October 2026

## Scope and baseline

Reviewed the general and legacy entry points, CSV ingestion and cleaning,
statistics, fitting, uncertainty, visualization, shared exports, optional
provider configuration/report validation, agent execution and audit, CI,
demo and existing tests. This is a targeted code and behavior review, not a
formal security audit, independent statistical certification, exhaustive
line-by-line review, or proof that every input or feature is correct. The
starting offline baseline for this session was 530 passed and 2 live-provider
skips. Changes are small and covered by regression tests; the final run is
recorded in the platform checklist.

## Corrections in this checkup

- **CSV:** an oversized or malformed field in the Python CSV parser now yields
  a user-facing import error rather than an uncaught parser exception. The
  parser's per-field size limit still applies even below the overall 5 MiB
  upload limit. Duplicate detection now handles a quoted multiline header.
- **Statistics and fits:** a mean interval no longer reports non-identical
  tiny values as identical when its standard error underflows. Fits whose
  squared diagnostics underflow are refused rather than reporting artificial
  zero error. The linear intercept-error calculation avoids prematurely
  squaring a large X offset. Exponential evaluation no longer silently clips
  exponents; an overflowing prediction is flagged undefined. This does not
  guarantee numerical accuracy across arbitrary magnitudes or models.
- **Weights:** a shared conversion validates representable, finite, positive
  inverse variances in the dashboard, CLI and agent. The agent now aligns the
  uncertainty values with the actual selected X/Y pair mask, not a different
  previously suggested pair mask. The dashboard starts with no uncertainty
  selected; invalid weights are not applied and the dashboard warns that it
  fell back to an unweighted fit. The CLI and agent reject invalid weights.
- **Agent:** each bounded tool runs with isolated context. A timeout closes
  the remaining tool budget and a late-running worker cannot mutate the
  recorded state. Tool exception text is passed through configured-secret
  redaction. Python threads cannot be forcibly terminated: a timed-out worker
  may still occupy a worker thread until it finishes, on its isolated copy.
- **CLI exports:** preflight all export names and reject a target equal to or
  hard-linked to the input, and symlinked descendants of the chosen output
  directory, before writing any artifact. Existing regular output files can
  still be replaced on repeated runs; choose a fresh directory to retain old
  results. The checks are not a defense against a concurrent adversary
  modifying the output tree between preflight and write, and do not change the
  separate legacy CLI's file-writing behavior.
- **Prediction UI:** an undefined model output is no longer described as an
  extrapolation. Conditional linear mean and individual prediction intervals
  are available only for the stated unweighted model assumptions.

## Remaining limitations and external work

- Full generalized/correlated uncertainty, arbitrary scientific domains,
  document/literature grounding, grounded chat, PDF/DOCX, advanced comparisons
  and other broader platform scope are not complete. See
  `PLATFORM_IMPLEMENTATION_CHECKLIST.md`.
- Tests and a scripted headless Chromium walkthrough cannot establish a
  scientific model's assumptions, accessibility, production security,
  Windows runtime behavior or correctness for every dataset. Cross-platform CI
  runs on GitHub after a push; it was not rerun remotely for unpushed changes.
- Live Muse Spark is optional and remains unverified here. Offline mock output
  is not an AI response. The recording, real user validation, rules/portal
  confirmation and submission require human participation and/or service
  access; no win or impact measurement is claimed.
