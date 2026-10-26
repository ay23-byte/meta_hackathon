"""Tests for the command-line entry point and its exported artifacts."""

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

import analyze_experiment
from analysis_core import analyze_linear, prepare_analysis_data

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_voltage_current.csv"


def test_cli_artifacts_match_the_shared_core(tmp_path):
    record = analyze_experiment.analyze_csv(SAMPLE, tmp_path)

    for name in (
        "analysis_results.json",
        "cleaned_and_fitted_data.csv",
        "voltage_current_fit.png",
        "residuals.png",
    ):
        assert (tmp_path / name).is_file(), name
        assert (tmp_path / name).stat().st_size > 0, name

    on_disk = json.loads(
        (tmp_path / "analysis_results.json").read_text(encoding="utf-8")
    )
    assert on_disk == record
    assert record["input_sha256"] == hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    assert record["application_version"] == "1.1.0"
    assert record["ai_interpretation_generated"] is False
    assert "centred" in record["method"]

    frame = pd.read_csv(SAMPLE)
    prepared = prepare_analysis_data(frame, "current_A", "voltage_V")
    expected = analyze_linear(prepared["current"], prepared["voltage"])
    assert record["slope_ohm"] == pytest.approx(expected["slope"])
    assert record["intercept_V"] == pytest.approx(expected["intercept"])
    assert record["r_squared"] == pytest.approx(expected["r_squared"])
    assert record["rmse_V"] == pytest.approx(expected["rmse"])
    assert record["n"] == expected["n"]
    assert record["row_counts"]["retained"] == expected["n"]

    cleaned = pd.read_csv(tmp_path / "cleaned_and_fitted_data.csv")
    assert len(cleaned) == expected["n"]
    assert (
        cleaned["voltage_V"] - cleaned["fitted_voltage_V"]
    ).to_numpy() == pytest.approx(cleaned["residual_V"].to_numpy(), abs=1e-9)
    assert cleaned["source_row"].tolist() == list(range(1, expected["n"] + 1))


def test_cli_rejects_ambiguous_columns(tmp_path):
    bad = tmp_path / "ambiguous.csv"
    bad.write_text("Current,Current (A),Voltage\n1,2,3\n2,3,4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unambiguous"):
        analyze_experiment.analyze_csv(bad, tmp_path / "out")


def test_cli_rejects_unreadable_csv(tmp_path):
    with pytest.raises(ValueError, match="Could not read CSV"):
        analyze_experiment.analyze_csv(tmp_path / "does-not-exist.csv", tmp_path)


def test_cli_main_writes_to_a_chosen_output_dir(tmp_path, monkeypatch, capsys):
    output = tmp_path / "artifacts"
    monkeypatch.setattr(
        sys,
        "argv",
        ["analyze_experiment.py", str(SAMPLE), "--output-dir", str(output)],
    )

    analyze_experiment.main()

    assert (output / "analysis_results.json").is_file()
    printed = capsys.readouterr().out
    assert '"slope_ohm"' in printed
    assert "Saved reproducible analysis artifacts" in printed
