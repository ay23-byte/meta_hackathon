"""Conditional algebra and unit conversions, not experimental validation."""
import copy
import io
import json
import zipfile
from pathlib import Path

import pytest

from research_assistant import experiment_context, reliability_notes, theory_notes
from result_schema import export_bundle
from theory_engine import ohmic_chapter


def sample(x_unit="A", y_unit="V", slope=4.99090909090909):
    return {"source": {"name": "synthetic.csv", "rows": 11, "sha256": "a" * 64},
            "roles": {"x": "current", "y": "voltage", "unit_x": x_unit, "unit_y": y_unit},
            "fit": {"success": True, "model": "linear", "parameters": {"slope": slope, "intercept": 0.00545455},
                    "metrics": {"r2": 0.999803}, "n_observations": 11},
            "statistics": {}, "cleaning": {}, "domain": {}, "correlation": {}, "outliers": {},
            "model_comparison": [], "visualizations": [], "notes": [], "warnings": []}


def test_unconfirmed_does_not_infer_theory_or_use_headers():
    chapter = ohmic_chapter(sample(), experiment_context())
    assert chapter["status"] == "context_needed" and not chapter["sections"]
    assert chapter["derived"] is None and chapter["missing"]


@pytest.mark.parametrize("x,y,slope,expected", [
    ("A", "V", 4.990909, 4.990909), ("mA", "V", 0.005, 5),
    ("A", "mV", 5000, 5), ("µA", "mV", 0.005, 5),
])
def test_ohmic_unit_conversion_and_immutability(x, y, slope, expected):
    result = sample(x, y, slope)
    before = copy.deepcopy(result)
    chapter = ohmic_chapter(result, experiment_context(confirmed_ohmic=True))
    assert chapter["derived"]["value"] == pytest.approx(expected)
    assert chapter["derived"]["source"] == "fit.parameters.slope and user-selected axis units"
    assert chapter["derived"]["status"] == "model_based_not_independently_verified"
    assert result == before


@pytest.mark.parametrize("unit,model,slope", [("s", "linear", 5), ("A", "power", 5), ("A", "linear", float("nan"))])
def test_missing_units_invalid_model_or_slope_does_not_report_resistance(unit, model, slope):
    result = sample(unit, "V", slope)
    result["fit"]["model"] = model
    chapter = ohmic_chapter(result, experiment_context(confirmed_ohmic=True))
    assert chapter["derived"] is None and chapter["missing"]


@pytest.mark.parametrize("level", ["beginner", "undergraduate", "postgraduate", "research"])
def test_levels_keep_the_same_computed_value_and_label_illustrative_example(level):
    chapter = ohmic_chapter(sample(), experiment_context(confirmed_ohmic=True, level=level))
    text = " ".join(part for section in chapter["sections"] for part in section["body"])
    assert "R = V/I" in text and "not experimental proof" in text
    assert "not measurements from the uploaded file" in text
    assert chapter["derived"]["value"] == pytest.approx(4.99090909090909)
    assert chapter["completeness"]["literature"] == "not_verified"


def test_zip_json_and_markdown_preserve_provenance_and_untrusted_text_safety():
    result = sample()
    context = experiment_context(title="<img src=x>", confirmed_ohmic=True)
    result["research"] = {"context": context, "theory": theory_notes(result, context),
                          "reliability": reliability_notes(result), "chapter": ohmic_chapter(result, context)}
    files = export_bundle(result)
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    with zipfile.ZipFile(io.BytesIO(buff.getvalue())) as archive:
        stored = json.loads(archive.read("results.json"))
        md = archive.read("report.md").decode()
    assert stored["fit"]["parameters"]["slope"] == result["fit"]["parameters"]["slope"]
    assert stored["research"]["chapter"]["derived"]["value"] == pytest.approx(4.99090909090909)
    assert "Conditional theory chapter" in md and "not measurements" in md
    assert "<img" not in md and "references were not retrieved or verified" in md


def test_ui_shows_conditional_chapter_only_after_confirmation():
    from streamlit.testing.v1 import AppTest

    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    next(w for w in at.checkbox if w.label == "Include offline theory and reliability notes").check().run()
    assert not at.exception and any("Confirm that X represents" in w.value for w in at.warning)
    next(w for w in at.checkbox if w.label.startswith("I confirm X is current")).check().run()
    assert not at.exception and not at.error
    assert any("Conditional resistance from current fit: 4.99091 ohm" in item.value for item in at.text)
    assert any("not measurements from the uploaded file" in item.value for item in at.text)


def test_chapter_uses_actual_bundled_data_fit(tmp_path):
    from analyze_dataset import analyze_csv

    path = Path(__file__).resolve().parents[1] / "data" / "sample_voltage_current.csv"
    result = analyze_csv(path, tmp_path, x="current_A", y="voltage_V", unit_x="A", unit_y="V")
    original = copy.deepcopy(result["fit"])
    chapter = ohmic_chapter(result, experiment_context(confirmed_ohmic=True))
    assert result["fit"]["n_observations"] == 11
    assert chapter["derived"]["value"] == pytest.approx(4.9909090909, abs=1e-8)
    assert result["fit"]["parameters"]["intercept"] == pytest.approx(0.00545454545, abs=1e-8)
    assert result["fit"]["metrics"]["r2"] == pytest.approx(0.999802959, abs=1e-8)
    assert result["fit"] == original
