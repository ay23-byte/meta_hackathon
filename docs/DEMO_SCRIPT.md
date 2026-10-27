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
summary: 229 passed, 2 skipped, 91% coverage of the new deterministic
modules — and state that the two skips are live provider tests.

## Alternative: general-platform demo (added 27 Oct 2026)

Run `python -m streamlit run general_app.py`. A 3-minute sequence that shows
the platform is not limited to the voltage-current sample:

1. **A - Upload**: start with the bundled sample, then upload
   `data/examples/synthetic_calibration.csv` (different column names, units,
   an uncertainty column and a group column).
2. **B - Validate / Clean**: show the inferred column kinds, the missing /
   invalid / non-finite counts and the cleaning preview; point out that
   nothing becomes zero and invalid rows stay in the cleaned CSV.
3. **C - Configure**: change X/Y, select the uncertainty column, switch the
   model to polynomial and then back to linear, and open the domain
   assumptions expander. Show that `generic` names no physical constant.
4. **D - Explore**: switch the primary chart between scatter, box,
   correlation heatmap and residuals; read one chart warning aloud.
5. **E - Fit**: show the equation, parameter errors, R², AIC comparison and
   an extrapolated prediction flagged as such.
6. **F - Interpret**: with a key configured, generate a report and state
   explicitly that it is AI-generated and unverified; without a key, show the
   graceful fallback.
7. **G - Export**: download the ZIP and open `report.md`, `results.json`
   and one `plots/*.html` file.

Never present the synthetic example data as real measurements.

## Agent demo (add ~45 s)

Run `python run_agent_demo.py --case all --strict` in a terminal beside the app.
Point at the console table: rows labelled **AI DECISION** are plan/selection
steps; **DETERMINISTIC TOOL** rows are computed numbers. Then show:

- Case A: `DONE`, 0 retries, conclusion cites R2 from the tool output.
- Case B: linear fit fails diagnostics, the validated `polynomial` alternative
  is selected, 1 retry, then `DONE`.
- Case B': `INSUFFICIENT_EVIDENCE` with an explicit reason - no invented
  conclusion.
- Case C: missing/invalid/inf detected, all 9 rows retained, 6 pairs used.
- Case C': `NEEDS_CLARIFICATION` before any fit.

Open `outputs/agent_demo/b/agent_report.md` and show the plan validation block,
the retry entry, the evidence refs and the Mermaid timeline. In the Streamlit
app, tick "Run the bounded analysis agent" to show the same audit trail inline
and note that `agent/` files are inside the exported ZIP.

State plainly: with no key, the plan comes from the deterministic fallback;
with a key, Muse Spark proposes it and the same validation applies. Do not
claim a live Muse-planned run was demonstrated unless a key was actually
configured and the log shows `plan_source: muse_spark`.

## After recording

- [ ] Watch the whole video: no API key, `.env`, or secret is visible.
- [ ] Confirm audio is clear and all claims match the app on screen.
- [ ] Confirm the video length against the current rule in the portal.
- [ ] Upload to the required host and put the link in the submission form.
- [ ] Verify the repository is visible to judges if a public repo is required.

See `docs/HACKATHON_RULES.md` for verified requirements and
`docs/HACKATHON_CHECKLIST.md` for the full submission checklist.
