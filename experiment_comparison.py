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
