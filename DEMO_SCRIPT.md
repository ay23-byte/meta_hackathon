# 90-second LabLens AI demo

1. **0–10 s:** Open the dashboard on the bundled sample. Say: “Lab data analysis often jumps from spreadsheet to conclusion without an auditable path. LabLens keeps the calculation deterministic and makes interpretation optional.”
2. **10–25 s:** Show the source preview, detected current/voltage selections, units, and research question. Point out the provenance note and retained/dropped counts.
3. **25–45 s:** Show slope, intercept, R², RMSE, fit plot, and residual plot. Say the numbers come from the tested Python analysis core, and R² does not prove the physical model.
4. **45–58 s:** Show the explorer table. Compare an in-range candidate with an out-of-range candidate; state that predictions are hypothetical and extrapolation is unsupported by the measured range.
5. **58–75 s:** Press “Generate evidence-grounded interpretation” only if `BASETEN_API_KEY` is configured and network access is available. Explain that Muse Spark receives a compact result summary, not raw measurements. Show sections and evidence-linked claims.
6. **75–90 s:** Show the Markdown, CSV, and JSON downloads. Point to the record's source hash, cleaning counts, model, and AI-used flag.

## If the network or API key is unavailable

Skip the API request and show the local numerical dashboard and report. Explain that Muse Spark is optional and that missing credentials/provider access does not affect calculation, plots, or downloads. Never expose the key in the recording.
