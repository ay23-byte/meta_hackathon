# Mathematical uncertainty: implemented scope

The application computes local 95% Student-t confidence intervals for the slope and intercept of an existing **successful, unweighted linear fit**, only when residual degrees of freedom are positive and both parameter estimates and residual-based standard errors are finite. For each parameter, the interval is `estimate ± t(0.975, n − 2) × standard_error`, using the same fit result and paired observations. No second regression is run. Units use the user-selected axis units; missing units are labelled unspecified. The interval and evidence paths are available in the UI, JSON and Markdown/ZIP export.

These intervals are **conditional** on the chosen linear model and independent, normally distributed errors with constant variance and effectively fixed X. These assumptions are not verified by producing an interval. Intervals quantify parameter sampling uncertainty under that model; they are **not prediction intervals** and do not quantify instrument accuracy, uncertainty in X, calibration, systematic effects, model-selection uncertainty or causal evidence. Header-derived units remain unverified hints.

Intervals are explicitly unavailable for failed, nonlinear, weighted or unspecified-weight fits, two-point fits (no residual degrees of freedom), and nonfinite/missing errors. For weighted linear fits, parameter standard errors use the absolute inverse-variance covariance `(Xᵀ W X)⁻¹`, assuming the supplied standard uncertainties are correct and independent; they are not scaled by residual scatter. This agrees with the nonlinear fitter’s absolute-sigma convention. For unweighted two-point fits, residual-based parameter errors are unavailable rather than inferred from zero residuals. No claim of weighted-fit confidence coverage is made. No user-supplied measurement uncertainty is invented or substituted.

The existing descriptive-statistics mean t intervals are separate, have their own assumptions, and do not describe regression parameters. General error propagation, Monte Carlo analysis, parameter intervals for other model types and comprehensive metrological uncertainty budgets remain unimplemented. Conditional unweighted linear prediction intervals are described below.

Tests: `python -m pytest -q tests/test_uncertainty_engine.py tests/test_fitting_core.py tests/test_statistics_core.py tests/test_result_schema.py`. An analytical synthetic example validates both parameter errors and the interval formula. Automated tests cannot establish that a real experiment meets statistical assumptions.

## User-supplied first-order propagation

The optional **Propagate user-supplied standard uncertainties** panel supports
sum, difference, product and ratio of two entered values using first-order
partial derivatives and `u(z) = sqrt((dz/da * u(a))² + (dz/db * u(b))²)`.
The user must supply each value, its nonnegative standard uncertainty and a
unit label, then explicitly confirm zero covariance; the confirmation resets
when any input changes. Nothing is inferred from the uploaded dataset. Use `1`
for dimensionless inputs. Sum/difference require identical unit strings;
product/ratio display compound labels but do not perform dimensional analysis
or unit conversion. A zero denominator is rejected and a denominator within
three supplied standard uncertainties of zero receives a warning.

This is a local first-order approximation, not a confidence interval, prediction
interval, complete uncertainty budget or calibration assessment. It assumes
uncorrelated inputs, omits systematic effects and higher-order terms, and can be
unreliable for nonlinear functions or high relative uncertainty. User-entered
values and the conditional result are included in JSON and Markdown/ZIP only
when confirmed; they are not sent to AI. Review inputs for sensitive content
before export. General symbolic formulas, correlated inputs, Monte Carlo and
automatic derivation of measurement uncertainties remain unsupported.

## Conditional linear mean-response and prediction intervals

For a successful **unweighted** linear fit with at least three finite pairs,
the follow-up explorer can calculate two-sided 95% Student-t intervals for
the mean response and for a single independent future observation. At a given
`x0`, with residual standard error `s`, sample size `n`, mean fitted X
`xbar` and `Sxx = sum((x - xbar)^2)`, the respective half-widths are
`t * s * sqrt(1/n + (x0-xbar)^2/Sxx)` and
`t * s * sqrt(1 + 1/n + (x0-xbar)^2/Sxx)`. The latter is typically wider
because it includes a future observation's residual variation.

These are model-based, not measurements; they assume a linear mean, fixed X,
independent normally distributed constant-variance errors, and, for a new
observation, the same error distribution. They do not cover calibration, X
uncertainty, systematic errors or model selection. A perfect synthetic fit
can produce near-zero widths; this is not proof of instrument accuracy.
Extrapolations are explicitly flagged and may be especially unreliable.
Weighted, nonlinear, failed, two-point and nonfinite fits are refused; there
is a maximum of 50 user-supplied candidates. The UI's current candidates and
intervals are included in JSON and Markdown/ZIP, not the AI context. The CLI
does not currently expose this interval workflow.
