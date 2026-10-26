
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

    selected = pd.DataFrame({
        "source_row": np.arange(1, len(frame) + 1),
        "current": pd.to_numeric(frame[current_col], errors="coerce"),
        "voltage": pd.to_numeric(frame[voltage_col], errors="coerce"),
    })

    current = selected["current"].to_numpy(dtype=float, na_value=np.nan)
    voltage = selected["voltage"].to_numpy(dtype=float, na_value=np.nan)
    valid = np.isfinite(current) & np.isfinite(voltage)

    clean = selected.loc[valid].copy().reset_index(drop=True)
    clean.rename(
        columns={"current": "current_A", "voltage": "voltage_V"},
        inplace=True,
    )

    return {
        "data": clean,
        "current": clean["current_A"].to_numpy(dtype=float),
        "voltage": clean["voltage_V"].to_numpy(dtype=float),
        "original_rows": int(len(frame)),
        "valid_rows": int(len(clean)),
        "dropped_rows": int(len(frame) - len(clean)),
    }


def analyze_linear(current, voltage):
    """Fit V = mI + b using ordinary least squares."""
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

    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    residuals = y - fitted

    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y))**2))

    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "fitted": fitted.tolist(),
        "residuals": residuals.tolist(),
        "r_squared": float(1 - ss_res / ss_tot) if ss_tot > 0 else None,
        "rmse": float(np.sqrt(np.mean(residuals**2))),
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
