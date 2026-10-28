"""Insights must be deterministic, traceable, and conditional on actual results."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from fitting_core import fit_linear
from insight_engine import discover_insights
from result_schema import ai_context, build_result, export_bundle
from statistics_core import outlier_diagnostics


def result_for(x, y, *, excluded=0, removed=0, unit_x="s", unit_y="mV"):
    return build_result(
        source={"rows": len(x) + excluded + removed, "columns": ["x", "y"], "name": "test.csv"},
        roles={"x": "x", "y": "y", "unit_x": unit_x, "unit_y": unit_y},
        cleaning={"rows_in": len(x) + excluded + removed, "rows_out": len(x) + excluded,
                  "invalid_pair_rows_excluded": excluded, "duplicates_removed": removed},
        statistics={}, correlation={}, outliers=outlier_diagnostics(y), fit=fit_linear(x, y),
        model_comparison=[], model_suggestions=[], domain={}, chart_summaries=[])


def test_exact_linear_fit_traceable_and_deterministic():
    x = np.arange(8, dtype=float)
    result = result_for(x, 2.5 * x + 1)
    before = copy.deepcopy(result)
    insights = discover_insights(result)
    assert result == before and insights == result["insights"]
    cards = insights["items"]
    assert 3 <= len(cards) <= 5
    fit = next(c for c in cards if c["id"] == "linear_fit")
    assert "Slope = 2.5 mV/s; intercept = 1 mV" in fit["observation"]
    assert "not identify its cause" in fit["limitations"]
    assert [c["priority"] for c in cards] == sorted([c["priority"] for c in cards], reverse=True)
    for card in cards:
        assert card["label"] == "Directly computed" and card["rank_reason"]
        for path in card["evidence_paths"]:
            obj = result
            for key in path.split("."):
                obj = obj[key]


def test_exclusions_and_outliers_take_priority_not_automatic_deletion():
    x = np.arange(8, dtype=float)
    result = result_for(x, [1, 1, 1, 1, 2, 2, 2, 100], excluded=2, removed=1)
    cards = result["insights"]["items"]
    assert [card["id"] for card in cards[:3]] == ["excluded_pairs", "duplicates_removed", "outlier_flags"]
    flag = cards[2]
    assert "not automatically errors" in flag["interpretation"]
    assert "do not remove automatically" in flag["next_step"]


def test_small_or_failed_fit_does_not_generate_strong_fit_claims():
    result = result_for([0, 1], [0, 5])
    ids = [card["id"] for card in result["insights"]["items"]]
    assert "limited_sample" in ids and "linear_fit" not in ids and "fit_diagnostics" not in ids
    result["fit"] = {"success": False, "model": "linear", "n_observations": 0, "metrics": {}}
    assert "linear_fit" not in [card["id"] for card in discover_insights(result)["items"]]
    assert discover_insights({})["status"] == "insufficient_information"


def test_nonfinite_and_constant_values_do_not_create_false_r2():
    result = result_for(np.arange(6), [5] * 6)
    cards = result["insights"]["items"]
    assert "fit_diagnostics" not in [card["id"] for card in cards]
    result["fit"]["parameters"]["slope"] = float("nan")
    assert "linear_fit" not in [card["id"] for card in discover_insights(result)["items"]]


def test_unsupported_model_and_missing_units_no_physics_inferred():
    result = result_for(np.arange(6), np.arange(6), unit_x="", unit_y="")
    assert "unspecified Y unit/unspecified X unit" in result["insights"]["items"][0]["observation"]
    assert "resistance" not in json.dumps(result["insights"]).lower()
    result["fit"]["model"] = "polynomial"
    assert "linear_fit" not in [c["id"] for c in discover_insights(result)["items"]]


def test_exports_escape_untrusted_units_and_exclude_insights_from_provider_context():
    result = result_for(np.arange(6), np.arange(6), unit_y='<img src=x>')
    exports = export_bundle(result)
    saved = json.loads(exports["results.json"])
    assert saved["insights"] == result["insights"]
    report = exports["report.md"].decode()
    assert "Key insights (deterministic)" in report and "<img" not in report
    assert "insights" not in ai_context(result)


def test_bundled_sample_uses_actual_fit_and_ui(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from analyze_dataset import analyze_csv

    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    root = Path(__file__).resolve().parents[1]
    result = analyze_csv(root / "data/sample_voltage_current.csv", tmp_path,
                         x="current_A", y="voltage_V", unit_x="A", unit_y="V")
    card = next(c for c in result["insights"]["items"] if c["id"] == "linear_fit")
    assert result["fit"]["parameters"]["slope"] == pytest.approx(4.9909090909)
    assert "Slope = 4.99091 V/A; intercept = 0.00545455 V" in card["observation"]
    at = AppTest.from_file(str(root / "general_app.py"), default_timeout=180).run()
    assert not at.exception and not at.error
    assert any(w.value == "Key insights" for w in at.subheader)
    assert any("Slope = 4.99091" in item.value for item in at.text)
    assert len(at.get("download_button")) == 3


def test_header_unit_hint_is_disclosed_and_user_can_correct():
    from streamlit.testing.v1 import AppTest

    root = Path(__file__).resolve().parents[1]
    at = AppTest.from_file(str(root / "general_app.py"), default_timeout=180).run()
    assert any("defaults inferred from column names" in w.value for w in at.warning)
    next(w for w in at.text_input if w.label == "X unit (optional)").set_value("mA").run()
    assert not at.exception and not at.error
    assert any("V/mA" in t.value for t in at.text if "Slope =" in t.value)
