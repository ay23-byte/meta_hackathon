# Evaluation plan

## Numerical correctness

- Test exact and noisy linear relationships, residual identity (`observed - fitted`), RMSE and R² formulas, constant voltage behavior, constant current rejection, invalid pairs, and repeatability.
- Check alias resolution and ambiguity behavior, dropped-row counts, original row numbering, and equality between dashboard/CLI core calls.
- Parse exported JSON strictly and check that CSV predictions and residuals match the deterministic analysis.

## AI claim grounding

- Use fixed mocked model responses; never require live calls in offline tests.
- Validate required JSON sections and claim fields, and test malformed JSON fallback, empty output, timeout, rate-limit, and missing-key paths.
- Compare every model-stated numerical value with the deterministic result; label unmatched values unverified. Verify that unsupported conclusions are described as hypotheses and that limitations appear.
- A live Muse Spark request is optional and must be run deliberately with the user's configured account.

## Failure modes and reproducibility

- Try empty/malformed files, ambiguous columns, same selected column, nonnumeric and infinite rows, too few pairs, and constant x.
- Re-run with original input bytes and selected columns, then compare fit parameters and cleaned paired rows. Check source hashes match identical bytes and differ after input changes.
- Test CSV/JSON/Markdown downloads without writing to project output directories.

## Baseline comparison

Compare the manual spreadsheet/script workflow and LabLens using the same fixed input and a predefined checklist: valid rows, selected variables, model equation, parameters, residual review, limitations, and ability to reproduce results. Record task completion and errors from observed sessions. Do not invent time saved, performance gains, scientific findings, or user adoption.
