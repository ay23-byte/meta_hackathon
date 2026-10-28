# User guide: current supported workflow

Run `python -m streamlit run general_app.py` from the repository root after
installing dependencies. Upload a supported delimited text file or use the
bundled example. Inspect data quality and the cleaning preview, choose roles,
units and a model, then inspect the deterministic Key insights cards, statistics,
plots, residuals and extrapolation warnings. Verify unit hints: column names do not
establish units. In **Research context and offline learning**, enable the notes and
provide only non-sensitive metadata. Confirm the Ohmic model only when you
know X is current, Y is voltage and the assumptions are reasonable; the app
does not establish this from a filename or a fit. Read the conditional theory
chapter and its missing-information warnings; the illustrative example is not
experimental data.

The live interpretation button sends a bounded computed summary only after an
explicit click and requires optional provider credentials. The offline mock is
a separate labelled deterministic template, never a substitute for a failed
live request. Review results and download JSON, cleaned CSV and ZIP. The optional
chapter is included in the JSON and Markdown report when enabled; user-entered
metadata is exported too. The current application does not implement literature
search, PDF ingestion, textbook-wide theory, grounded experiment chat or
multi-dataset comparison. See `SCIENTIFIC_THEORY_ENGINE.md`,
`PROVIDER_INTEGRATION.md` and `IMPLEMENTATION_PROGRESS.md`.

### Plotting uploaded observations

The general app plots the current upload after cleaning, using the selected
numeric X and Y columns. Select a primary chart and, optionally, a grouping
column. X/Y plots require at least two numeric columns and two complete finite
pairs in this workflow, even for a histogram or box plot. Column previews and
cleaning counts appear before the chart; chart notes report valid/excluded rows
and any display cap. Choose **Overlay selected fitted model on scatter** only
when the selected model is appropriate: the line is a prediction, not measured
data or evidence of causality. The analysis still computes the selected model,
which defaults to linear as an exploratory starting point; change it as needed.
Labels use selected units, which must be verified, especially header-derived
hints. The ZIP export contains available HTML and local PNG chart files. HTML
plots need access to the Vega-Lite CDN when opened; PNGs do not.

### Residual diagnostics

In **Primary chart**, select **Residuals vs fitted values (requires a fit)** to
plot the selected model's residuals against its fitted Y values. The other
residual plot uses selected X. Residuals are observed minus fitted; curves,
clusters or changing spread can suggest a need to investigate model or error
assumptions, but neither a pattern nor its absence proves a cause or validates
the model. No instrument uncertainty is inferred. The chart is included in
existing HTML/PNG bundle exports when selected and is capped at 50,000 points.

### Compare two experiments

After the first analysis, open **Compare a second experiment (offline)**.
Upload another file, map X/Y, enter matching units and confirm the quantities,
methods and conditions are comparable. Review the separate counts, means and
scatter before interpreting the descriptive difference. See
[comparison limits](EXPERIMENT_COMPARISON.md); no unit conversion or
independent scientific compatibility check is performed.

### Confidence intervals for a linear fit

Open **Parameter confidence intervals (conditional)** in the fit section.
For successful unweighted linear fits with sufficient residual degrees of
freedom, the app reports 95% slope/intercept t intervals. Read the assumptions:
these intervals are not prediction intervals or instrument accuracy. Weighted
and nonlinear fit intervals are not implemented. See
[uncertainty scope](MATHEMATICS_AND_UNCERTAINTY.md).

### Propagate supplied uncertainties

Open **Propagate user-supplied standard uncertainties**, enable the calculator,
choose an operation and enter the two values, standard uncertainties and unit
labels. Confirm the values and zero-covariance assumption. Inputs are not taken
from your upload. Review the first-order approximation and any ratio warning;
this is not instrument calibration or a confidence interval. Confirmed inputs
are included in the JSON and Markdown report. See
[uncertainty scope](MATHEMATICS_AND_UNCERTAINTY.md).
