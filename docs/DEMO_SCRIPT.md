# LabLens AI demo script and recording guide

Target length: **about 2:45** (leaves headroom under the widely cited
three-minute community guideline; the official rules we read do not state a
length, so confirm in the participant portal). A truthful, executable demo
using the bundled sample dataset.

Never present a mock or saved AI report as a live Muse Spark result. If the
API is unavailable, use the fallback path below and say so on camera.

## Pre-recording checklist

- [ ] `python -m pytest -m "not live" -q` passes; `ruff check .` passes.
- [ ] `python -m streamlit run app.py` opens with the bundled sample.
- [ ] Either a working `BASETEN_API_KEY` in a local `.env`, **or** a plan to
      use the fallback path (no key).
- [ ] Hide your terminal, `.env`, browser password manager, and any key
      while recording. Set the browser zoom so text is legible at 1080p.
- [ ] Close unrelated tabs/notifications. Use a wired connection if possible.
- [ ] Rehearse once. If recording live AI, do a private warm-up call first
      so latency is predictable; the video must still show the real call.
- [ ] Do not claim measured time savings, user adoption, or verified
      experimental results — none were measured.

## Shot list

### 0:00–0:20 — The problem (wide shot, hero)

> "Lab data analysis often jumps from a spreadsheet to a conclusion without
> an auditable path. LabLens keeps the calculation deterministic, makes the
> cleaning explicit, and makes AI interpretation optional and
> evidence-grounded."

Show the hero, then the sidebar: scientific safeguards, AI provider status,
workflow steps, and the "Built with Muse Spark Open" attribution. Say
explicitly whether a key is configured.

### 0:20–0:45 — Upload and map data

Show the preview of `data/sample_voltage_current.csv` (11 rows), detected
column selections, units (A, V), and the research question. Point out that
provenance is "not independently verified" and that column mapping is
confirmed by the user, not guessed silently. Mention the input SHA-256 that
will appear in the export.

### 0:45–1:15 — Deterministic fit and diagnostics

Show slope ≈ 4.99091 V/A, intercept ≈ 0.00545 V, R² ≈ 0.999803,
RMSE ≈ 0.02216 V. Say these come from the tested Python core, not from AI.
Show the fit plot and residual plot. Emphasize:

- R² does not prove the physical model;
- invalid paired rows are counted and excluded, never silently dropped;
- no outliers are removed automatically;
- no instrument uncertainty or confidence intervals are claimed.

Optional credibility beat (5 s): mention the regression test that catches
large-offset numerical instability — evidence of engineering depth.

### 1:15–1:40 — Hypothetical follow-up (explorer)

Show the explorer table. Compare one candidate inside [0, 1] A with one
outside it. State that predictions are model outputs, hypothetical, and
that out-of-range predictions are extrapolations unsupported by the data.

### 1:40–2:10 — AI interpretation (configured path only)

Press "Generate evidence-grounded interpretation". While it loads, explain:

- Muse Spark receives only a compact result summary — never the raw CSV and
  never the API key;
- the request uses a developer instruction and JSON mode;
- the response is validated against a strict eight-section schema with
  evidence-linked claims before it is shown;
- a context hash binds the report to the currently displayed analysis.

Show the eight sections and the claims table. Say: "These statements are
not independently verified; check them against the numerical record."

**Fallback (no key / provider error):** skip the generation and instead
show the sidebar status and a failed/omitted attempt. Say on camera:

> "Muse Spark is optional. Missing credentials or provider access does not
> affect calculation, plots, or exports. The offline tests verify the
> request and validation contract; the live round-trip needs a key."

Never show a mocked report as a live result.

### 2:10–2:30 — Export reproducibility

Download all three files. Open the Markdown report and JSON record on
screen. Point to: source filename, input SHA-256, original/retained row
counts, cleaning policy, model and method, metrics, warnings, software
versions, and the AI-used flag.

### 2:30–2:45 — Close

> "Reproducible calculations first, optional evidence-grounded AI second,
> with uncertainty and limitations shown explicitly."

End on the residual plot or the exported JSON. Optionally flash the test
summary: 112 passed, 2 skipped, 98% coverage — and state that the two
skips are live provider tests.

## After recording

- [ ] Watch the whole video: no API key, `.env`, or secret is visible.
- [ ] Confirm audio is clear and all claims match the app on screen.
- [ ] Confirm the video length against the current rule in the portal.
- [ ] Upload to the required host and put the link in the submission form.
- [ ] Verify the repository is visible to judges if a public repo is required.

See `docs/HACKATHON_RULES.md` for verified requirements and
`docs/HACKATHON_CHECKLIST.md` for the full submission checklist.
