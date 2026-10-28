# Research assistant: offline foundation

## Scope implemented

The optional **Research context and offline learning** panel captures a user
provided title, discipline, description, apparatus/method, conditions, equation,
and explanation level. This is explicitly unverified user input. Confirming
that X is current and Y is voltage enables an offline explanation of the
assumption `V = IR` and its algebraic relation to `R = V / I`; this confirmation
is a user assertion, not inference from column names. It does not establish the
law or the origin of an intercept. Unrecognized units and a non-linear or
failed fit generate cautions. Different detail levels include different notes,
not an independently authored educational curriculum.

Reliability notes state whether the selected fit actually uses weights, that
outliers are flags, and that independence, instrument calibration, systematic
error and accuracy are not established by the data. They do not invent
uncertainties or calculate new confidence intervals, bootstrap estimates,
power or influence statistics. Existing statistics, fit and parameters remain
authoritative. Numbers are not copied into the new notes; the existing fit
section of the report displays them directly from the result record.

The existing comparison panel allows selection among already-computed models,
shows their in-range curves and residuals (display capped at 2,000 residuals
per model), and preserves the currently selected fit. The application uses the
same complete X/Y pairs and weights for the candidate fits; models whose domain
is invalid are rejected. AIC is meaningful only with comparable samples and
weighting and compatible likelihood assumptions. It is not proof of causation,
and no cross-validation or automatic scientific recommendation is performed.
For datasets above 5,000 fitted pairs the comparison evaluates linear,
polynomial, and the selected model rather than every nonlinear candidate.

If enabled, the additive `research` field in the existing result JSON contains
context, text notes and provenance. The Markdown and ZIP export contain the
same notes and the existing authoritative calculation sections. Context and
notes are recomputed on every rerun, and changes invalidate stored AI report
state. The new research context is **not sent** by the existing AI report
context builder; existing AI interactions and their explicit consent remain
unchanged. Review user-entered context before exporting because it may contain
sensitive information. No new network requests occur.

## Not implemented

Grounded conversational Q&A, multi-dataset comparison, external source
retrieval and claim-to-reference verification, comprehensive theory/derivation
for other scientific disciplines, new uncertainty estimation methods,
cross-validation, a full research-report builder, and PDF export are not
implemented by this increment. No external citations were retrieved or verified.
The existing markdown/JSON/ZIP artifacts continue to work without AI. The
existing report AI provider is optional and live provider behaviour is not
verified by offline tests. This increment is not an independent scientific
review or guarantee of validity.

## Use

Run `python -m streamlit run general_app.py`, load a supported dataset and
configure its columns, units and fit. In **Research context and offline
learning**, enable notes and optionally confirm the physical assumptions. Read
**Theory and reliability** and **Compare candidate models**; export as before.
The confirmed ohmic explanation must only be selected when the user knows that
X represents current and Y voltage. No provider key is needed for these notes.
