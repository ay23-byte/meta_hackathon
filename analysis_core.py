
"""Deterministic numerical and data-preparation functions for LabLens AI."""

import json
import re

import numpy as np
import pandas as pd

CURRENT_ALIASES = {
    "current", "currenta", "currentamp", "currentamps", "currentampere",
    "currentamperes", "amps", "amp", "ampere", "amperes", "i", "ia",
}
VOLTAGE_ALIASES = {
    "voltage", "voltagev", "potential", "potentialdifference",
    "volts", "volt", "v", "vv",
}


def _normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", str(name).casefold())


def detect_candidate_columns(columns, measurement):
    """Detect a column only when exactly one confident alias matches."""
    if measurement == "current":
        aliases = CURRENT_ALIASES
    elif measurement == "voltage":
        aliases = VOLTAGE_ALIASES
    else:
        raise ValueError("measurement must be 'current' or 'voltage'.")

    matches = [col for col in columns if _normalize_name(col) in aliases]
    return matches[0] if len(matches) == 1 else None


def prepare_analysis_data(frame, current_col, voltage_col):
    """Convert selected measurements to numeric and exclude invalid pairs."""
    if current_col == voltage_col:
        raise ValueError("Choose different columns for current and voltage.")

    missing = [c for c in (current_col, voltage_col) if c not in frame.columns]
    if missing:
        raise ValueError(f"Selected column not found: {', '.join(map(str, missing))}.")
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("The CSV contains no data rows.")

    if frame.columns.duplicated().any():
        duplicates = ", ".join(
            map(str, frame.columns[frame.columns.duplicated()].unique())
        )
        raise ValueError(
            "Duplicate column names are not allowed: "
            f"{duplicates}. Rename them before uploading."
        )

    # Convert to positional NumPy arrays before building the result frame.
    # Passing labelled Series into a DataFrame constructor can align on a
    # non-default index on some pandas versions, silently mis-pairing rows.
    current = pd.to_numeric(frame[current_col], errors="coerce").to_numpy(
        dtype=float, na_value=np.nan
    )
    voltage = pd.to_numeric(frame[voltage_col], errors="coerce").to_numpy(
        dtype=float, na_value=np.nan
    )

    selected = pd.DataFrame({
        "source_row": np.arange(1, len(frame) + 1),
        "current": current,
        "voltage": voltage,
    })

    valid = np.isfinite(current) & np.isfinite(voltage)

    clean = selected.loc[valid].copy().reset_index(drop=True)
    clean = clean.rename(
        columns={"current": "current_A", "voltage": "voltage_V"},
    )

    return {
        "data": clean,
        "current": clean["current_A"].to_numpy(dtype=float),
        "voltage": clean["voltage_V"].to_numpy(dtype=float),
        "original_rows": len(frame),
        "valid_rows": len(clean),
        "dropped_rows": int(len(frame) - len(clean)),
    }


def analyze_linear(current, voltage):
    """Fit V = mI + b using ordinary least squares.

    The slope is computed from centred variables
    ``sum((x-xbar)(y-ybar)) / sum((x-xbar)^2)`` and the intercept from
    ``ybar - slope*xbar``. This is algebraically the same OLS line as
    ``np.polyfit`` but stays accurate when measurements have a large offset
    relative to their spread (e.g. currents recorded around 1e9 A), where
    an uncentred design matrix can produce a badly wrong intercept.

    R² is ``1 - ss_res/ss_tot`` and is ``None`` when ``ss_tot == 0``
    (constant voltage), because R² is undefined rather than zero there.
    RMSE uses denominator n, not n-2.
    """
    x = np.asarray(current, dtype=float).reshape(-1)
    y = np.asarray(voltage, dtype=float).reshape(-1)

    if x.size != y.size:
        raise ValueError("Current and voltage must have equal lengths.")
    if x.size < 2:
        raise ValueError("At least two measurements are required.")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("Measurements must be finite numbers.")
    if np.ptp(x) == 0:
        raise ValueError("Current measurements must vary to estimate a slope.")

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            x_center = x - x.mean()
            y_center = y - y.mean()
            denominator = float(np.dot(x_center, x_center))

            if denominator <= 0 or not np.isfinite(denominator):
                raise ValueError(
                    "Current spread is too small to estimate a slope reliably."
                )

            slope = float(np.dot(x_center, y_center) / denominator)
            intercept = float(y.mean() - slope * x.mean())
            fitted = slope * x + intercept
            residuals = y - fitted

            ss_res = float(np.dot(residuals, residuals))
            ss_tot = float(np.dot(y_center, y_center))
            r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else None
            rmse = float(np.sqrt(np.mean(residuals**2)))
    except FloatingPointError as exc:
        raise ValueError(
            "Measurements are too large or too closely spaced for a "
            "reliable floating-point fit."
        ) from exc

    if not np.all(np.isfinite([slope, intercept, rmse])):
        raise ValueError("The fitted line produced non-finite results.")
    if not np.all(np.isfinite(fitted)) or not np.all(np.isfinite(residuals)):
        raise ValueError("The fitted line produced non-finite predictions.")

    return {
        "slope": slope,
        "intercept": intercept,
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "r_squared": r_squared,
        "rmse": rmse,
        "n": int(x.size),
    }


def propose_measurements(candidate_currents, analysis, observed_currents):
    """Predict hypothetical voltages and flag extrapolation."""
    candidates = np.asarray(candidate_currents, dtype=float).reshape(-1)
    observed = np.asarray(observed_currents, dtype=float).reshape(-1)

    if candidates.size == 0 or not np.all(np.isfinite(candidates)):
        raise ValueError("Provide finite proposed current values.")
    if observed.size == 0 or not np.all(np.isfinite(observed)):
        raise ValueError("Observed current values are unavailable.")

    low, high = float(np.min(observed)), float(np.max(observed))

    return pd.DataFrame({
        "proposed_current_A (hypothetical)": candidates,
        "predicted_voltage_V (model prediction)": (
            analysis["slope"] * candidates + analysis["intercept"]
        ),
        "within_observed_range": (candidates >= low) & (candidates <= high),
        "distance_from_observed_range_A": (
            np.maximum(low - candidates, 0) + np.maximum(candidates - high, 0)
        ),
    })


def serialize_analysis_exports(record, cleaned_data, report_markdown):
    """Return JSON, CSV, and Markdown export strings."""
    def safe(value):
        if isinstance(value, dict):
            return {str(k): safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [safe(v) for v in value]
        if isinstance(value, np.ndarray):
            return safe(value.tolist())
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, (np.floating, float)):
            return float(value) if np.isfinite(value) else None
        return value

    return {
        "json": json.dumps(safe(record), indent=2, allow_nan=False),
        "csv": cleaned_data.to_csv(index=False),
        "markdown": str(report_markdown),
    }
