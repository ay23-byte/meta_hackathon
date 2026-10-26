"""Run the deterministic LabLens analysis from a CSV file."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe on Windows, Linux and CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis_core import analyze_linear, detect_candidate_columns, prepare_analysis_data

ROOT = Path(__file__).resolve().parent


def analyze_csv(csv_path, output_dir):
    """Run the shared deterministic core and write reproducible artifacts."""
    csv_path = Path(csv_path)
    try:
        raw_bytes = csv_path.read_bytes()
        frame = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError,
            UnicodeDecodeError) as exc:
        raise ValueError(f"Could not read CSV: {type(exc).__name__}") from exc

    current_col = detect_candidate_columns(frame.columns, "current")
    voltage_col = detect_candidate_columns(frame.columns, "voltage")
    if current_col is None or voltage_col is None:
        raise ValueError(
            "Could not identify one unambiguous current and voltage column; "
            "use the dashboard to select columns."
        )

    prepared = prepare_analysis_data(frame, current_col, voltage_col)
    result = analyze_linear(prepared["current"], prepared["voltage"])

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cleaned = prepared["data"].copy()
    cleaned["fitted_voltage_V"] = result["fitted"]
    cleaned["residual_V"] = result["residuals"]
    cleaned.to_csv(output_dir / "cleaned_and_fitted_data.csv", index=False)

    record = {
        "application": "LabLens AI",
        "application_version": "1.1.0",
        "source_file": csv_path.name,
        "input_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "software_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "selected_columns": {
            "current": str(current_col),
            "voltage": str(voltage_col),
        },
        "row_counts": {
            "original": prepared["original_rows"],
            "retained": prepared["valid_rows"],
            "dropped": prepared["dropped_rows"],
        },
        "cleaning_policy": (
            "Selected columns converted to numeric; rows with missing, "
            "nonnumeric, NaN, or infinite values excluded. No automatic "
            "outlier removal; source row order preserved."
        ),
        "model": "V = mI + b",
        "method": "Unweighted ordinary least squares, centred normal equations",
        "slope_ohm": result["slope"],
        "intercept_V": result["intercept"],
        "r_squared": result["r_squared"],
        "rmse_V": result["rmse"],
        "rmse_convention": "sqrt(mean(residual^2)) using denominator n",
        "r_squared_note": "None when voltage has zero variance (undefined).",
        "n": result["n"],
        "warnings": [
            "High R-squared does not establish physical correctness.",
            "Instrument uncertainty and calibration are not included.",
            "Provenance is unknown unless described by the user; not verified.",
        ],
        "provenance": "unknown; not independently verified",
        "ai_interpretation_generated": False,
    }
    (output_dir / "analysis_results.json").write_text(
        json.dumps(record, indent=2, allow_nan=False), encoding="utf-8"
    )

    x, y = prepared["current"], prepared["voltage"]
    order = np.argsort(x)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(x, y, label="Observed measurements")
    ax.plot(x[order], np.asarray(result["fitted"])[order], label="OLS fitted model")
    ax.set(
        xlabel="Current (selected units)",
        ylabel="Voltage (selected units)",
        title="Voltage-current analysis",
    )
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "voltage_current_fit.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axhline(0, color="black", linewidth=1)
    ax.scatter(x, result["residuals"])
    ax.set(
        xlabel="Current (selected units)",
        ylabel="Residual (selected voltage units)",
        title="Residuals against current",
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "residuals.png", dpi=160)
    plt.close(fig)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, default=ROOT / "data" / "sample_voltage_current.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    result = analyze_csv(args.csv, args.output_dir)
    print(json.dumps(result, indent=2))
    print(f"Saved reproducible analysis artifacts to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
