"""Reproducible synthetic demo dataset contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import analyze_dataset

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo" / "linear_calibration_demo.csv"
README = ROOT / "data" / "demo" / "README.md"


def test_demo_dataset_is_documented_as_synthetic():
    text = README.read_text(encoding="utf-8").casefold()
    assert "synthetic" in text and "not experimental" in text


def test_demo_cli_produces_known_computed_results(tmp_path):
    result = analyze_dataset.analyze_csv(
        DEMO, tmp_path, x="time_s", y="signal_mV", model="linear",
        research_question="How does signal_mV vary with time_s?",
        report_profile="scientific", generate_mock=True,
    )
    assert result["source"]["rows"] == 15
    assert result["cleaning"]["rows_out"] == 15
    assert result["cleaning"]["invalid_pair_rows_excluded"] == 3
    assert result["fit"]["n_observations"] == 12
    assert result["fit"]["parameters"]["slope"] == pytest.approx(2.5, abs=1e-9)
    assert result["fit"]["parameters"]["intercept"] == pytest.approx(0.1, abs=1e-9)
    assert result["fit"]["metrics"]["r2"] == pytest.approx(1.0, abs=1e-12)
    assert result["fit"]["metrics"]["rmse"] == pytest.approx(0.0, abs=1e-12)

    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert data["ai"]["source"] == "offline_mock"
    assert data["ai"]["is_mock"] is True
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "OFFLINE MOCK report (deterministic template, NOT AI)" in report
    assert "slope=2.5" in report and "R²=1" in report
    cleaned = (tmp_path / "cleaned_data.csv").read_text(encoding="utf-8-sig")
    assert len(cleaned.strip().splitlines()) == 16  # header + 15 retained rows


def test_demo_selectable_in_main_app_without_upload():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "general_app.py"), default_timeout=60).run()
    examples = next(item for item in app.selectbox if item.label == "Or load a bundled synthetic example")
    assert DEMO.name in examples.options
    examples.select(DEMO.name).run()
    assert not app.exception
    assert any("Synthetic demonstration data" in item.value for item in app.info)
    assert any("15" in str(item.value) for item in app.metric)


def test_demo_does_not_automatically_apply_inferred_uncertainties():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "general_app.py"), default_timeout=60).run()
    next(w for w in app.selectbox if w.label == "Or load a bundled synthetic example").select(DEMO.name).run()
    sigma = next(w for w in app.selectbox if w.label == "Uncertainty column (1 sigma)")
    assert sigma.value == "(none)"
    sigma.select("sigma_mV").run()
    assert not app.exception and not app.error
    assert any("absolute inverse variances" in warning.value for warning in app.warning)
