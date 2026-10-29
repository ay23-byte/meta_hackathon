"""Bounded, offline comparison of two explicitly mapped experiments.

The confirmation is a user assertion, not verification of compatibility.
No inference from filenames, automatic unit conversion or pooled fit is done.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from data_io import coerce_numeric

MAX_COMPARISON_POINTS = 2000


def prepare_pairs(frame: pd.DataFrame, x: str, y: str) -> tuple[np.ndarray, np.ndarray]:
    """Return finite positional pairs without changing the source frame."""
    if x == y or x not in frame.columns or y not in frame.columns:
        raise ValueError("Choose two different existing columns for each experiment.")
    xv, yv = coerce_numeric(frame[x]).values, coerce_numeric(frame[y]).values
    valid = np.isfinite(xv) & np.isfinite(yv)
    return xv[valid], yv[valid]


def compare_experiments(first: dict, second: dict, *, confirmed: bool) -> tuple[dict, pd.DataFrame]:
    """Compare two finite paired sets using explicitly matching unit strings.

    Each input contains a frame, selected column names, user-provided units,
    name, and source SHA-256. No independent unit or variable validation is
    claimed. Return exportable summary plus bounded plot data separately.
    """
    if not confirmed:
        raise ValueError("Confirm that both mapped variables, units and methods are comparable.")
    for axis in ("unit_x", "unit_y"):
        a, b = first.get(axis), second.get(axis)
        if not isinstance(a, str) or not isinstance(b, str) or not a.strip() or not b.strip():
            raise ValueError("Both experiments need explicit nonempty X and Y units; conversions are not supported.")
        if a.strip() != b.strip():
            raise ValueError("Units must match exactly for each axis; automatic conversion is not supported.")
    summaries = []
    plot_parts = []
    for index, experiment in enumerate((first, second), start=1):
        frame = experiment["frame"]
        x, y = prepare_pairs(frame, experiment["x"], experiment["y"])
        if len(x) < 2:
            raise ValueError(f"Experiment {index} needs at least two complete finite X/Y pairs.")
        with np.errstate(over="ignore", invalid="ignore"):
            mean_x, mean_y = float(np.mean(x)), float(np.mean(y))
        if not (math.isfinite(mean_x) and math.isfinite(mean_y)):
            raise ValueError(f"Experiment {index} has nonfinite summary values; check numerical range.")
        summaries.append({
            "dataset": f"Experiment {index}", "source_name": str(experiment.get("name") or ""),
            "source_sha256": str(experiment.get("sha256") or ""),
            "x_column": experiment["x"], "y_column": experiment["y"],
            "unit_x": experiment["unit_x"].strip(), "unit_y": experiment["unit_y"].strip(),
            "rows_before_pair_exclusion": len(frame), "valid_pairs": len(x),
            "excluded_pairs": len(frame) - len(x), "mean_x": mean_x, "mean_y": mean_y,
            "points_displayed": min(len(x), MAX_COMPARISON_POINTS),
        })
        count = min(len(x), MAX_COMPARISON_POINTS)
        plot_parts.append(pd.DataFrame({"x": x[:count], "y": y[:count],
                                        "dataset": f"Experiment {index}"}))
    difference = summaries[1]["mean_y"] - summaries[0]["mean_y"]
    if not math.isfinite(difference):
        raise ValueError("Difference in means is nonfinite; check numerical range.")
    return ({"status": "user_confirmed_not_independently_verified", "datasets": summaries,
             "mean_y_difference_second_minus_first": difference,
             "method": "Descriptive mean of finite paired values; no unit conversion or pooled fit.",
             "limitations": "Compatibility, methods and conditions are user assertions. First-dataset cleaning choices may differ from the second dataset, where duplicates are retained. Means may reflect differing X ranges, sampling, or conditions; differences do not establish causation or statistical significance. No uncertainty or independent replication is inferred.",
             "plot_note": f"First {MAX_COMPARISON_POINTS} complete pairs per experiment at most; no interpolation or extrapolation."},
            pd.concat(plot_parts, ignore_index=True))


def independent_mean_difference_interval(first: dict, second: dict, *, confirmed: bool) -> dict:
    """Two-sided Welch interval for mean Y difference, under explicit assumptions.

    This does not adjust for X, confounding, repeated measures or pairing.
    """
    from scipy.stats import t

    # Reuse compatibility validation and pair exclusion before any inference.
    summary, _ = compare_experiments(first, second, confirmed=confirmed)
    if not confirmed:
        raise ValueError("Confirm the assumptions before computing this interval.")
    _, a = prepare_pairs(first["frame"], first["x"], first["y"])
    _, b = prepare_pairs(second["frame"], second["x"], second["y"])
    with np.errstate(all="ignore"):
        sa, sb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
        va, vb = sa / len(a), sb / len(b)
        total = va + vb
    if (not all(math.isfinite(v) for v in (sa, sb, total)) or total <= 0 or
            (sa == 0 and np.any(a != a[0])) or (sb == 0 and np.any(b != b[0]))):
        raise ValueError("The mean-difference interval is unavailable because estimated variance is zero, nonfinite or underflowed.")
    # Normalizing first avoids overflow from squaring very large variances.
    denominator = (va / total)**2 / (len(a) - 1) + (vb / total)**2 / (len(b) - 1)
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("The Welch degrees of freedom are unavailable.")
    dof = 1 / denominator
    critical = float(t.ppf(.975, dof))
    difference = summary["mean_y_difference_second_minus_first"]
    margin = critical * math.sqrt(total)
    lower, upper = difference - margin, difference + margin
    if not all(math.isfinite(v) for v in (dof, critical, margin, lower, upper)):
        raise ValueError("The mean-difference interval is nonfinite; rescale the measurements.")
    return {"status": "conditional", "difference_second_minus_first": difference,
            "lower": lower, "upper": upper, "unit": summary["datasets"][0]["unit_y"],
            "degrees_of_freedom": dof, "standard_error": math.sqrt(total),
            "method": "Two-sided 95% Welch t interval for the difference in paired-valid Y means, experiment 2 minus experiment 1.",
            "assumptions": "Independent observations within and between experiments; approximately normal Y values or sufficient samples. Sampling and protocol comparability are user assertions.",
            "limitations": "Not a paired or repeated-measures analysis. Does not adjust for differing X distributions, conditions, systematic errors or multiple comparisons. "
                           "The interval does not establish causation, equivalence or practical significance."}
