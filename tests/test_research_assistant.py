"""Offline research notes use explicit context and preserve computed results."""
import copy
import json
from pathlib import Path

import pytest

from research_assistant import experiment_context, reliability_notes, theory_notes
from result_schema import export_bundle


def sample_result():
    return {"source": {"name": "synthetic.csv", "sha256": "a" * 64, "rows": 11},
            "roles": {"x": "current", "y": "voltage", "unit_x": "A", "unit_y": "V"},
            "fit": {"success": True, "model": "linear", "n_observations": 11,
                    "weighted": False, "parameters": {"slope": 4.990909, "intercept": 0.00545455},
                    "metrics": {"r2": 0.999803}},
            "statistics": {}, "cleaning": {}, "domain": {}, "correlation": {},
            "outliers": {}, "model_comparison": [], "visualizations": [], "notes": [], "warnings": []}


def test_ambiguous_data_never_infers_ohmic_theory():
    result = sample_result()
    theory = theory_notes(result, experiment_context())
    assert theory["status"] == "context_needed"
    assert not any("V = I R" in line for line in theory["notes"])


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
def test_confirmed_theory_is_labelled_and_does_not_change_calculations(level):
    result = sample_result()
    original = copy.deepcopy(result)
    theory = theory_notes(result, experiment_context(confirmed_ohmic=True, level=level))
    assert theory["status"] == "user_confirmed_assumption"
    assert any("V = I R" in line for line in theory["notes"])
    assert any("not proof" in line for line in theory["notes"])
    assert result == original


def test_units_and_failed_or_non_linear_fit_are_not_mislabelled():
    result = sample_result()
    result["roles"]["unit_x"] = "s"
    result["fit"]["model"] = "power"
    theory = theory_notes(result, experiment_context(confirmed_ohmic=True))
    assert any("unrecognised" in line for line in theory["notes"])
    assert any("not a successful linear fit" in line for line in theory["notes"])


def test_reliability_distinguishes_uncertainty_weights():
    result = sample_result()
    assert any("No measurement uncertainty" in line for line in reliability_notes(result)["notes"])
    result["roles"]["uncertainty"] = "sigma"
    assert any("unweighted" in line for line in reliability_notes(result)["notes"])
    result["fit"]["weighted"] = True
    assert any("inverse-variance" in line for line in reliability_notes(result)["notes"])


def test_export_contains_theory_and_authoritative_metrics_without_html_injection():
    result = sample_result()
    ctx = experiment_context(title='<img src=x> [click](https://example.com)', confirmed_ohmic=True)
    result["research"] = {"context": ctx, "theory": theory_notes(result, ctx),
                          "reliability": reliability_notes(result)}
    files = export_bundle(result)
    stored = json.loads(files["results.json"])
    assert stored["fit"]["parameters"]["slope"] == 4.990909
    report = files["report.md"].decode()
    assert "4.99091" in report and "V = I R" in report
    assert "<img" not in report and "[click](https://example.com)" not in report
    assert "references were not retrieved or verified" in report


def test_invalid_explanation_level_is_rejected():
    with pytest.raises(ValueError, match="Explanation level"):
        experiment_context(level="invented")


def test_ui_offline_research_section_tracks_explicit_confirmation():
    from streamlit.testing.v1 import AppTest

    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    next(w for w in at.checkbox if w.label == "Include offline theory and reliability notes").check().run()
    assert not at.exception and not at.error
    assert any("No physical theory has been confirmed" in t.value for t in at.text)
    next(w for w in at.checkbox if w.label.startswith("I confirm X is current")).check().run()
    assert not at.exception and not at.error
    assert any("V = I R" in t.value for t in at.text)
    assert any("4.99091" == metric.value for metric in at.metric)
    assert "V = I R" in " ".join(t.value for t in at.get("code"))


def test_ui_research_context_change_invalidates_existing_mock():
    from streamlit.testing.v1 import AppTest

    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    next(b for b in at.button if "OFFLINE MOCK" in b.label).click().run()
    assert any("OFFLINE MOCK report" in item.value for item in at.markdown)
    next(w for w in at.checkbox if w.label == "Include offline theory and reliability notes").check().run()
    assert not at.exception and not at.error
    assert not any("### OFFLINE MOCK report" in item.value for item in at.markdown)


def test_comparison_selection_keeps_selected_fit_and_draws_charts():
    from streamlit.testing.v1 import AppTest

    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    widget = next(m for m in at.multiselect if m.label == "Candidate models to compare")
    assert "linear" in widget.value
    assert any(metric.value == "4.99091" for metric in at.metric)
    assert len(at.get("vega_lite_chart")) >= 2
