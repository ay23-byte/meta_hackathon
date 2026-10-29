"""Evidence references point to actual analysis values, never invented rows."""
import copy
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from analyze_dataset import analyze_csv
from evidence_trace import build_evidence_ledger
from result_schema import export_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_current_insights_link_to_actual_values_and_export(tmp_path):
    result = analyze_csv(ROOT / "data/sample_voltage_current.csv", tmp_path, x="current_A", y="voltage_V")
    ledger = result["evidence_ledger"]
    items = {item["id"]: item for item in ledger["items"]}
    for link in ledger["insight_links"]:
        assert link["evidence_ids"] and not link["missing_paths"]
        assert all(identifier in items for identifier in link["evidence_ids"])
    slope = next(item for item in items.values() if item["result_path"] == "fit.parameters.slope")
    assert slope["value"] == result["fit"]["parameters"]["slope"]
    files = export_bundle(result)
    assert json.loads(files["results.json"])["evidence_ledger"] == ledger
    assert slope["id"] in files["report.md"].decode()


def test_changed_inputs_invalidate_references_and_missing_paths_are_explicit(tmp_path):
    result = analyze_csv(ROOT / "data/sample_voltage_current.csv", tmp_path)
    old = build_evidence_ledger(result)
    edited = copy.deepcopy(result)
    edited["fit"]["parameters"]["slope"] += 1
    new = build_evidence_ledger(edited)
    assert new["analysis_fingerprint"] != old["analysis_fingerprint"]
    assert not {item["id"] for item in old["items"]} & {item["id"] for item in new["items"]}
    del edited["fit"]["parameters"]["slope"]
    incomplete = build_evidence_ledger(edited)
    assert "fit.parameters.slope" in incomplete["unavailable_paths"]
    assert any("fit.parameters.slope" in link["missing_paths"] for link in incomplete["insight_links"])


def test_second_experiment_summary_is_linked_without_raw_rows(tmp_path):
    result = analyze_csv(ROOT / "data/sample_voltage_current.csv", tmp_path)
    result["comparison"] = {"mean_y_difference_second_minus_first": 2.0, "datasets": [{"valid_pairs": 4}]}
    ledger = build_evidence_ledger(result)
    assert any(i["result_path"] == "comparison.mean_y_difference_second_minus_first" and i["value"] == 2.0 for i in ledger["items"])
    assert "frame" not in json.dumps(ledger)


def test_demo_is_labelled_synthetic_and_has_inspectable_evidence():
    app = AppTest.from_file(str(ROOT / "general_app.py"), default_timeout=120).run()
    next(w for w in app.selectbox if w.label == "Or load a bundled synthetic example").select("linear_calibration_demo.csv").run()
    assert not app.exception and not app.error
    assert any(w.label == "Inspect evidence behind these insights" for w in app.expander)
    evidence = next(df for df in app.dataframe if "source_kind" in df.value.columns)
    assert set(evidence.value["source_kind"]) == {"synthetic_demonstration"}


def test_exported_mock_claim_ids_resolve_to_sent_evidence(tmp_path):
    result = analyze_csv(ROOT / "data/demo/linear_calibration_demo.csv", tmp_path,
                         x="time_s", y="signal_mV", generate_mock=True)
    assert result["source"]["data_origin"] == "synthetic_demonstration"
    ai = result["ai"]
    assert ai["source"] == "offline_mock"
    assert ai["evidence_index"]
    for claim in ai["structured"]["claims"]:
        assert all(identifier in ai["evidence_index"] for identifier in claim["evidence_ids"])
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "AI context evidence index" in report
    assert all(identifier in report for claim in ai["structured"]["claims"] for identifier in claim["evidence_ids"])
