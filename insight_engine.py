"""Deterministic, bounded summaries of the existing scientific result.

Ranking is a fixed priority order, not a statistical confidence or a measure
of scientific importance. No raw data, domain inference or network access.
"""
from __future__ import annotations

import math


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def discover_insights(result: dict) -> dict:
    """Summarize available evidence; never recompute fits or infer a theory.

    Evidence paths point into the same result record. Small-sample thresholds
    govern presentation only and do not establish statistical adequacy.
    """
    source = result.get("source") or {}
    cleaning = result.get("cleaning") or {}
    roles = result.get("roles") or {}
    fit = result.get("fit") or {}
    outliers = result.get("outliers") or {}
    cards = []

    def present(path):
        value = result
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return False
            value = value[part]
        return True

    def add(identifier, priority, title, observation, interpretation, evidence, limitation, next_step, why):
        cards.append({"id": identifier, "priority": priority, "title": title,
                      "label": "Directly computed", "observation": observation,
                      "interpretation": interpretation, "evidence_paths": [path for path in evidence if present(path)],
                      "limitations": limitation, "next_step": next_step, "rank_reason": why})

    excluded = cleaning.get("invalid_pair_rows_excluded")
    removed = cleaning.get("duplicates_removed")
    n = fit.get("n_observations")
    n = n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None
    if isinstance(excluded, int) and excluded > 0:
        add("excluded_pairs", 100, "Incomplete pairs excluded",
            f"{excluded} row(s) with invalid or incomplete selected X/Y pairs were excluded from fitting.",
            "The fitted result describes the retained pairs, which may not represent excluded rows.",
            ["cleaning.invalid_pair_rows_excluded", "fit.n_observations"],
            "Exclusion is not evidence that missingness is random or that a measurement is erroneous.",
            "Review the cleaning preview and investigate missing or invalid values.",
            "Data quality takes priority because exclusions can affect every fit.")
    if isinstance(removed, int) and removed > 0:
        add("duplicates_removed", 95, "Duplicate rows removed",
            f"{removed} duplicate row(s) were removed under the selected cleaning rule.",
            "The analysis describes the retained rows rather than all uploaded rows.",
            ["cleaning.duplicates_removed", "cleaning.rows_in", "cleaning.rows_out"],
            "Identical rows can be legitimate repeated measurements; duplication alone does not establish error.",
            "Check the cleaning rule and whether duplicates are independent repeats.",
            "The user-selected exclusion can affect all downstream results.")
    fit_dof = (fit.get("metrics") or {}).get("degrees_of_freedom")
    if n is not None and (n < 4 or (_finite(fit_dof) and fit_dof <= 0)):
        add("limited_sample", 90, "Limited evidence for model assessment",
            f"The selected fit uses {n} observation(s).",
            "This small or saturated fit provides limited ability to assess model adequacy.",
            ["fit.n_observations", "fit.metrics.degrees_of_freedom"],
            "The four-observation display threshold is a conservative heuristic, not a power calculation.",
            "Collect additional independent measurements across the range, if feasible.",
            "A small or saturated sample limits interpretation of the fit.")
    if outliers.get("valid"):
        low, high = outliers.get("n_low"), outliers.get("n_high")
        if isinstance(low, int) and isinstance(high, int) and low + high > 0:
            add("outlier_flags", 80, "Unusual response values flagged",
                f"IQR fences flag {low} low and {high} high selected Y value(s).",
                "These values merit review but are not automatically errors.",
                ["outliers.n_low", "outliers.n_high", "outliers.n_valid"],
                "IQR flags depend on the distribution and do not establish measurement error.",
                "Inspect the observations and compare results under documented choices; do not remove automatically.",
                "Flagged values can influence fitted parameters.")
    if fit.get("success") and fit.get("model") == "linear" and n is not None and n >= 4:
        params = fit.get("parameters") or {}
        slope, intercept = params.get("slope"), params.get("intercept")
        if _finite(slope) and _finite(intercept):
            xu, yu = roles.get("unit_x") or "unspecified X unit", roles.get("unit_y") or "unspecified Y unit"
            add("linear_fit", 70, "Selected linear fit",
                f"Slope = {slope:.6g} {yu}/{xu}; intercept = {intercept:.6g} {yu} (n = {n}).",
                "The slope describes the fitted change in Y per unit X; the intercept is the fitted Y value at X = 0.",
                ["fit.parameters.slope", "fit.parameters.intercept", "fit.n_observations", "roles.unit_x", "roles.unit_y"],
                "This depends on the selected linear model and correct units; an intercept may be extrapolated and does not identify its cause.",
                "Inspect residuals and the observed X range before attaching a physical interpretation.",
                "Fit parameters summarize the selected relationship in the measured sample.")
    metrics = fit.get("metrics") or {}
    r2, rmse, dof = metrics.get("r2"), metrics.get("rmse"), metrics.get("degrees_of_freedom")
    if fit.get("success") and n is not None and n >= 4 and _finite(r2) and _finite(rmse) and _finite(dof) and dof > 0:
        yu = roles.get("unit_y") or "unspecified Y unit"
        add("fit_diagnostics", 60, "Fit diagnostics",
            f"R² = {r2:.6g}; residual RMSE = {rmse:.6g} {yu}; residual degrees of freedom = {dof}.",
            "These summarize in-sample fit and residual magnitude for the selected model.",
            ["fit.metrics.r2", "fit.metrics.rmse", "fit.metrics.degrees_of_freedom", "roles.unit_y"],
            "R² is not proof of causation, model validity or calibrated uncertainty; RMSE is not instrument precision.",
            "Examine residual patterns and consider physically justified alternatives.",
            "Model diagnostics qualify the fitted relationship.")
    rows = source.get("rows")
    columns = source.get("columns")
    if n is not None and isinstance(rows, int) and isinstance(columns, list):
        add("coverage", 50, "Dataset and fit coverage",
            f"The source has {rows} row(s) and {len(columns)} column(s); the selected fit uses {n} observation(s).",
            "The fit uses selected complete pairs after the configured cleaning decisions.",
            ["source.rows", "source.columns", "fit.n_observations", "cleaning.rows_out"],
            "Row count is not the number of independent replicates; data collection and sampling are unknown.",
            "Review data types, missingness and the cleaning record.",
            "Coverage makes the analysis population explicit.")
    cards.sort(key=lambda card: (-card["priority"], card["id"]))
    return {"version": "1.0", "status": "available" if cards else "insufficient_information",
            "ranking": "Fixed order: exclusions, small-sample warning, outlier flags, selected fit, diagnostics, coverage; not a confidence score.",
            "items": cards[:5],
            "limitations": "Descriptive summaries only; no theory identification, causality or calibrated confidence is implied."}
