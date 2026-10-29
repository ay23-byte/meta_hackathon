"""Compact AI references cannot be reused for a different analysis."""
import copy
from pathlib import Path

from ai_guard import check_report_numbers
from analyze_dataset import analyze_csv
from result_schema import ai_context

ROOT = Path(__file__).resolve().parents[1]


def test_current_ids_are_bound_to_data_mapping_and_results(tmp_path):
    result = analyze_csv(ROOT / "data/demo/linear_calibration_demo.csv", tmp_path,
                         x="time_s", y="signal_mV")
    current = ai_context(result)
    assert current["result_ids"] == ai_context(copy.deepcopy(result))["result_ids"]
    claim = {"sections": [], "claims": [{"claim": "Inspect the fit.",
              "evidence_ids": [next(i for i in current["result_ids"] if i.startswith("fit."))]}]}
    assert check_report_numbers(claim, current)["status"] == "partially_checked"
    for path, value in [("source", "sha256"), ("roles", "unit_x"), ("fit", "model")]:
        changed = copy.deepcopy(result)
        changed[path][value] = "changed"
        other = ai_context(changed)
        assert not set(current["result_ids"]) & set(other["result_ids"])
        assert check_report_numbers(claim, other)["status"] == "contradiction"
