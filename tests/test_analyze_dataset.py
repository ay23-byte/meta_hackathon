"""General CLI: real artifacts, inference, weighting and clear failures."""

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

import analyze_dataset

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_voltage_current.csv"
EXAMPLES = ROOT / "data" / "examples"


def test_legacy_sample_works_with_general_cli(tmp_path):
    result = analyze_dataset.analyze_csv(
        SAMPLE, tmp_path, x="current_A", y="voltage_V",
        unit_x="A", unit_y="V", domain="ohmic",
    )
    assert result["fit"]["success"] is True
    assert result["fit"]["parameters"]["slope"] == pytest.approx(4.990909, abs=1e-5)
    assert result["source"]["sha256"] == hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    assert result["domain"]["derived"][0]["unit"] == "ohm"
    for name in ("results.json", "cleaned_data.csv", "statistics.csv",
                 "fit_parameters.csv", "fit_metrics.csv", "report.md",
                 "plots/scatter.html", "plots/scatter.png", "plots/residuals.png"):
        assert (tmp_path / name).is_file(), name
    assert json.loads((tmp_path / "results.json").read_text()) == result


def test_columns_are_inferred_when_not_supplied(tmp_path):
    result = analyze_dataset.analyze_csv(EXAMPLES / "synthetic_quadratic.csv", tmp_path)
    assert result["roles"]["x"] == "displacement_mm"
    assert result["roles"]["y"] == "restoring_force_N"
    assert result["source"]["name"] == "synthetic_quadratic.csv"


def test_weighted_calibration_fit_and_domain(tmp_path):
    result = analyze_dataset.analyze_csv(
        EXAMPLES / "synthetic_calibration.csv", tmp_path,
        x="concentration_uM", y="absorbance_570nm",
        uncertainty="abs_sigma", domain="calibration", unit_x="uM", unit_y="AU",
    )
    assert result["fit"]["weighted"] is True
    assert result["fit"]["parameters"]["slope"] == pytest.approx(0.082, abs=0.005)
    assert result["domain"]["derived"][0]["name"] == "sensitivity"
    assert "covariance" in result["correlation"]


def test_polynomial_and_exponential_models_export_successfully(tmp_path):
    quadratic = analyze_dataset.analyze_csv(
        EXAMPLES / "synthetic_quadratic.csv", tmp_path / "poly",
        x="displacement_mm", y="restoring_force_N", model="polynomial", degree=2,
    )
    assert quadratic["fit"]["parameters"]["c2"] == pytest.approx(0.35, abs=0.02)
    growth = analyze_dataset.analyze_csv(
        EXAMPLES / "synthetic_growth.csv", tmp_path / "growth",
        x="day", y="cell_count", model="exponential", domain="growth",
        unit_x="day",
    )
    assert growth["fit"]["success"] is True
    assert growth["domain"]["derived"][0]["name"] == "doubling time"


def test_messy_import_keeps_invalid_rows_in_cleaned_csv(tmp_path):
    # Generate the cp1252 bytes in-memory. A checked-in non-UTF-8 fixture can
    # be silently re-encoded by tooling (a workspace snapshot turned 0xB0 into
    # U+FFFD), which would make an encoding-fallback test fail for the wrong
    # reason. Encoding fallback is asserted separately in test_encoding_fallback.py.
    text = (
        "temperature_deg\u00b0C;pressure_kPa;replicate\n"
        "20.0;101.3;R1\n25.0;103.8;R1\n30.0;oops;R2\n35.0;108.1;R2\n"
        ";110.4;R3\n45.0;inf;R3\n50.0;114.7;R4\n55.0;117.2;R4\n"
    )
    path = tmp_path / "generated_cp1252.csv"
    path.write_bytes(text.encode("cp1252"))
    result = analyze_dataset.analyze_csv(path, tmp_path)
    cleaned = pd.read_csv(tmp_path / "cleaned_data.csv")
    assert len(cleaned) == result["source"]["rows"] == 8
    assert result["cleaning"]["rows_out"] == 8
    assert result["cleaning"]["invalid_pair_rows_excluded"] >= 2
    assert result["source"]["encoding"] == "cp1252"
    assert "temperature_deg\u00b0C" in result["source"]["columns"]


def test_clear_errors_for_invalid_config(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        analyze_dataset.analyze_csv(tmp_path / "missing.csv", tmp_path)
    with pytest.raises(ValueError, match="different columns"):
        analyze_dataset.analyze_csv(SAMPLE, tmp_path, x="current_A", y="current_A")
    with pytest.raises(ValueError, match="Unknown column"):
        analyze_dataset.analyze_csv(SAMPLE, tmp_path, x="nope")
    bad_sigma = tmp_path / "bad_sigma.csv"
    bad_sigma.write_text("x,y,sigma\n1,2,0.1\n2,4,0\n3,6,-1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="1-sigma"):
        analyze_dataset.analyze_csv(bad_sigma, tmp_path / "bad",
                                    x="x", y="y", uncertainty="sigma")


def test_main_reports_errors_without_tracebacks(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["analyze_dataset.py", str(tmp_path / "missing.csv")])
    assert analyze_dataset.main() == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Error:" in captured.err


def test_main_writes_artifacts_and_prints_summary(monkeypatch, tmp_path, capsys):
    output = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "analyze_dataset.py", str(SAMPLE), "--x", "current_A", "--y", "voltage_V",
        "--output-dir", str(output), "--model", "linear",
    ])
    assert analyze_dataset.main() == 0
    printed = capsys.readouterr().out
    assert "Fit successful: True" in printed
    assert (output / "results.json").is_file()


def test_ai_is_optional_and_missing_key_is_reported(monkeypatch, tmp_path):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    result = analyze_dataset.analyze_csv(SAMPLE, tmp_path, generate_ai=True)
    assert "not configured" in result["ai_note"]
    assert result.get("ai") is None
    assert (tmp_path / "results.json").is_file()


def test_ai_can_use_custom_sections_with_a_stub_provider(monkeypatch, tmp_path):
    import ask_muse

    monkeypatch.setenv("BASETEN_API_KEY", "unit-test-placeholder")
    titles = ["Data Quality and Cleaning", "Quantitative Results"]
    calls = []

    def fake(context, section_titles=None):
        calls.append((context, section_titles))
        return {"model": "stub", "structured": {"sections": [
            {"title": title, "content": "Deterministic-grounded note."} for title in titles
        ], "claims": []}}

    monkeypatch.setattr(ask_muse, "generate_interpretation", fake)
    result = analyze_dataset.analyze_csv(
        SAMPLE, tmp_path, generate_ai=True, section_titles=titles,
    )
    assert result["ai"]["structured"]["sections"][0]["title"] == titles[0]
    assert calls[0][1] == titles
    assert "fit" in calls[0][0]


def test_cli_offline_mock_is_labelled_and_question_is_recorded(monkeypatch, tmp_path):
    import ask_muse

    def forbidden(**kwargs):
        raise AssertionError("--ai-mock must not construct a provider client.")

    monkeypatch.setattr(ask_muse, "OpenAI", forbidden)
    assert analyze_dataset.main([
        str(SAMPLE), "--x", "current_A", "--y", "voltage_V",
        "--output-dir", str(tmp_path), "--ai-mock",
        "--report-profile", "scientific", "--question", "What is the slope?",
    ]) == 0
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    ai = data["ai"]
    assert ai["is_mock"] is True and ai["source"] == "offline_mock"
    assert ai["structured"]["sections"][0]["title"] == "Research Question"
    assert "What is the slope?" in json.dumps(ai["structured"], ensure_ascii=False)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "OFFLINE MOCK report" in report and "NOT AI" in report
    assert "4.99091" in report  # computed, not invented


def test_cli_agent_question_is_written_to_audit(tmp_path):
    question = "How does voltage_V vary with current_A?"
    assert analyze_dataset.main([
        str(SAMPLE), "--x", "current_A", "--y", "voltage_V",
        "--output-dir", str(tmp_path), "--agent", "--question", question,
    ]) == 0
    audit = json.loads((tmp_path / "agent" / "agent_audit.json").read_text(encoding="utf-8"))
    assert audit["research_question"] == question
    assert audit["question_source"] == "user"
    assert audit["final"]["state"] == "DONE"


def test_cli_rejects_unrepresentable_inverse_variance(tmp_path):
    source = tmp_path / "tiny_uncertainty.csv"
    source.write_text("x,y,sigma\n1,2,1e-200\n2,4,1e-200\n3,6,1e-200\n", encoding="utf-8")
    with pytest.raises(ValueError, match="numerical range"):
        analyze_dataset.analyze_csv(source, tmp_path / "out", x="x", y="y", uncertainty="sigma")
