"""Descriptive statistics for arbitrary numeric columns.

Every function reports how many observations it actually used. Population
and sample statistics are distinguished explicitly, and constant or
insufficient data produce a stated reason instead of a misleading number.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

DEFAULT_PERCENTILES = (5, 25, 50, 75, 95)


def _finite(values) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    return array[np.isfinite(array)]


def describe_numeric(values, *, ddof: int = 1) -> dict:
    """Return a full distribution summary with explicit validity accounting."""
    raw = np.asarray(values, dtype=object).reshape(-1)
    numeric = pd.to_numeric(pd.Series(raw), errors="coerce").to_numpy(dtype=float)
    n_total = int(numeric.size)
    n_nan = int(np.isnan(numeric).sum())
    n_infinite = int(np.isinf(numeric).sum())
    clean = numeric[np.isfinite(numeric)]
    n_valid = int(clean.size)
    ddof = int(ddof)

    result = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_missing_or_invalid": n_nan,
        "n_infinite": n_infinite,
        "ddof": ddof,
        "constant": bool(n_valid > 1 and np.ptp(clean) == 0),
        "valid": n_valid >= 2,
        "reason": None,
    }
    if n_valid == 0:
        result["valid"] = False
        result["reason"] = "No finite numeric observations are available."
        return result
    if n_valid < 2:
        result["valid"] = False
        result["reason"] = "At least two finite observations are required for dispersion statistics."

    with np.errstate(all="ignore"):
        mean = float(np.mean(clean))
        variance_sample = (float(np.var(clean, ddof=ddof))
                           if n_valid - ddof > 0 and n_valid >= 2 else None)
        std_sample = (float(np.std(clean, ddof=ddof))
                      if n_valid - ddof > 0 and n_valid >= 2 else None)
        variance_population = float(np.var(clean, ddof=0))
        std_population = float(np.std(clean, ddof=0))
        median = float(np.median(clean))
        q1 = float(np.percentile(clean, 25))
        q3 = float(np.percentile(clean, 75))
        percentiles = {str(pct): float(np.percentile(clean, pct))
                       for pct in DEFAULT_PERCENTILES}
    summaries = [mean, variance_population, std_population, median, q1, q3]
    summaries += [value for value in (variance_sample, std_sample) if value is not None]
    summaries += list(percentiles.values())
    if not all(math.isfinite(value) for value in summaries):
        # Very large (but finite) measurements can overflow mean/variance.
        # Report the usable order statistics and explicitly omit the rest.
        result["valid"] = False
        result["reason"] = ("Non-finite summary statistics; measurements may be too "
                            "large or too closely spaced for reliable computation.")
        result.update({
            "mean": mean if math.isfinite(mean) else None,
            "median": median if math.isfinite(median) else None,
            "min": float(np.min(clean)),
            "max": float(np.max(clean)),
            "q1": q1 if math.isfinite(q1) else None,
            "q3": q3 if math.isfinite(q3) else None,
            "percentiles": {key: (value if math.isfinite(value) else None)
                            for key, value in percentiles.items()},
            "iqr": q3 - q1 if math.isfinite(q1) and math.isfinite(q3) else None,
            "variance_sample": (variance_sample if variance_sample is not None
                                and math.isfinite(variance_sample) else None),
            "std_sample": (std_sample if std_sample is not None
                           and math.isfinite(std_sample) else None),
            "variance_population": (variance_population
                                    if math.isfinite(variance_population) else None),
            "std_population": (std_population
                               if math.isfinite(std_population) else None),
        })
        ci = confidence_interval_mean(clean)
        result["ci_mean_95"] = ci["interval"]
        result["ci_mean_method"] = ci["method"]
        return result

    result.update(
        {
            "mean": mean,
            "median": median,
            "min": float(np.min(clean)),
            "max": float(np.max(clean)),
            "q1": q1,
            "q3": q3,
            "percentiles": percentiles,
            "variance_sample": variance_sample,
            "std_sample": std_sample,
            "variance_population": variance_population,
            "std_population": std_population,
        }
    )
    result["iqr"] = q3 - q1

    ci = confidence_interval_mean(clean)
    result["ci_mean_95"] = ci["interval"]
    result["ci_mean_method"] = ci["method"]
    return result


def confidence_interval_mean(values, confidence: float = 0.95) -> dict:
    """Two-sided t interval for the mean; states its assumptions."""
    clean = _finite(values)
    n = int(clean.size)
    if n < 2:
        return {
            "interval": None,
            "method": "Not computed: at least two finite observations are required.",
            "assumptions": "Independent, approximately normal observations.",
        }
    with np.errstate(all="ignore"):
        sem = float(stats.sem(clean))
    if not math.isfinite(sem):
        return {
            "interval": None,
            "method": "Not computed: the standard error is non-finite; values may be too large.",
            "assumptions": "Independent, approximately normal observations.",
        }
    if sem == 0:
        if not np.all(clean == clean[0]):
            return {
                "interval": None,
                "method": "Not computed: standard error underflowed for non-identical values; rescale the data.",
                "assumptions": "Independent, approximately normal observations.",
            }
        return {
            "interval": [float(clean[0]), float(clean[0])],
            "method": "t interval degenerate: all finite values are identical.",
            "assumptions": "Independent, approximately normal observations.",
        }
    with np.errstate(all="ignore"):
        low, high = stats.t.interval(confidence, n - 1, loc=float(np.mean(clean)), scale=sem)
    return {
        "interval": [float(low), float(high)],
        "method": f"Two-sided {confidence:.0%} Student-t interval, df={n - 1}.",
        "assumptions": (
            "Independent, approximately normal observations. This is statistical "
            "uncertainty about the mean, NOT instrument measurement uncertainty."
        ),
    }


def correlation(x, y, method: str = "pearson") -> dict:
    """Pearson or Spearman correlation on pairwise-complete observations."""
    left = pd.to_numeric(pd.Series(np.asarray(x, dtype=object).reshape(-1)), errors="coerce").to_numpy(dtype=float)
    right = pd.to_numeric(pd.Series(np.asarray(y, dtype=object).reshape(-1)), errors="coerce").to_numpy(dtype=float)
    if left.size != right.size:
        return {"valid": False, "reason": "The two columns have different lengths.", "n_valid": 0}

    mask = np.isfinite(left) & np.isfinite(right)
    n_valid = int(mask.sum())
    base = {"method": method, "n_valid": n_valid, "valid": False, "reason": None}
    if method not in ("pearson", "spearman"):
        return {**base, "reason": f"Unsupported correlation method: {method}."}
    if n_valid < 3:
        return {**base, "reason": "At least three complete finite pairs are required."}
    a, b = left[mask], right[mask]
    if np.ptp(a) == 0 or np.ptp(b) == 0:
        return {**base, "reason": "Correlation is undefined for a constant column."}

    if method == "pearson":
        coefficient = float(np.corrcoef(a, b)[0, 1])
        test = stats.pearsonr(a, b)
    else:
        coefficient = float(stats.spearmanr(a, b).statistic)
        test = stats.spearmanr(a, b)
    p_value = float(getattr(test, "pvalue", float("nan")))
    return {
        **base,
        "valid": bool(np.isfinite(coefficient)),
        "coefficient": coefficient,
        "p_value": p_value if math.isfinite(p_value) else None,
        "n_excluded": int(left.size - n_valid),
        "reason": None if np.isfinite(coefficient) else "The coefficient is not finite.",
        "caveat": (
            "Correlation measures association, not causation. The p-value assumes "
            "independent observations and (for Pearson) an approximately linear "
            "relationship; it is not a test of a physical model."
        ),
    }


def covariance(x, y, *, ddof: int = 1) -> dict:
    left = pd.to_numeric(pd.Series(np.asarray(x, dtype=object).reshape(-1)), errors="coerce").to_numpy(dtype=float)
    right = pd.to_numeric(pd.Series(np.asarray(y, dtype=object).reshape(-1)), errors="coerce").to_numpy(dtype=float)
    if left.size != right.size:
        return {"valid": False, "n_valid": 0, "value": None, "ddof": ddof,
                "reason": "The two columns have different lengths."}
    mask = np.isfinite(left) & np.isfinite(right)
    n_valid = int(mask.sum())
    if n_valid <= ddof:
        return {"valid": False, "n_valid": n_valid, "value": None, "ddof": ddof,
                "reason": "Insufficient complete finite pairs for this ddof."}
    matrix = np.cov(left[mask], right[mask], ddof=ddof)
    value = float(matrix[0, 1])
    if not math.isfinite(value):
        return {"valid": False, "n_valid": n_valid, "value": None, "ddof": ddof,
                "reason": "Covariance is non-finite; values may be too large."}
    return {
        "valid": True,
        "n_valid": n_valid,
        "value": value,
        "ddof": ddof,
        "reason": None,
    }


def correlation_matrix(frame: pd.DataFrame, columns: list[str], method: str = "pearson") -> pd.DataFrame:
    """Pairwise correlation matrix; undefined entries stay NaN."""
    matrix = pd.DataFrame(np.nan, index=columns, columns=columns, dtype=float)
    for i, first in enumerate(columns):
        diagonal = correlation(frame[first], frame[first], method=method) if first in frame.columns else {}
        matrix.loc[first, first] = 1.0 if diagonal.get("valid") else np.nan
        for second in columns[i + 1:]:
            if first not in frame.columns or second not in frame.columns:
                continue
            result = correlation(frame[first], frame[second], method=method)
            value = result.get("coefficient") if result["valid"] else np.nan
            matrix.loc[first, second] = value
            matrix.loc[second, first] = value
    return matrix


def outlier_diagnostics(values) -> dict:
    """IQR-based outlier *flags* only — never removes observations."""
    clean = _finite(values)
    n = int(clean.size)
    if n < 4:
        return {
            "valid": False,
            "n_valid": n,
            "reason": "At least four finite observations are required for IQR fences.",
            "n_low": 0,
            "n_high": 0,
            "indices": [],
        }
    q1, q3 = np.percentile(clean, [25, 75])
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    flags = (clean < low) | (clean > high)
    return {
        "valid": True,
        "n_valid": n,
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(iqr),
        "lower_fence": float(low),
        "upper_fence": float(high),
        "n_low": int((clean < low).sum()),
        "n_high": int((clean > high).sum()),
        "indices": np.flatnonzero(flags).tolist(),
        "reason": None,
        "caveat": (
            "IQR fences are heuristic diagnostics, not proof of error. Outliers "
            "are NOT removed automatically; investigate their provenance."
        ),
    }


def descriptive_table(frame: pd.DataFrame, columns: list[str], *, ddof: int = 1) -> pd.DataFrame:
    """One row per statistic, one column per selected measurement."""
    summaries = {name: describe_numeric(frame[name], ddof=ddof) for name in columns if name in frame.columns}
    rows = [
        "n_valid", "n_missing_or_invalid", "n_infinite", "mean", "median",
        "std_sample", "std_population", "variance_sample", "variance_population",
        "min", "q1", "q3", "iqr", "max", "ci95_low", "ci95_high",
    ]

    def cell(name: str, row: str):
        summary = summaries[name]
        if row in ("ci95_low", "ci95_high"):
            interval = summary.get("ci_mean_95")
            if not interval:
                return None
            return interval[0] if row == "ci95_low" else interval[1]
        return summary.get(row)

    table = pd.DataFrame(
        {name: [cell(name, row) for row in rows] for name in summaries},
        index=rows,
    )
    return table.reset_index(names="statistic")
