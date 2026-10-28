"""Experiment comparison is descriptive and requires fresh explicit consent."""
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from experiment_comparison import MAX_COMPARISON_POINTS, compare_experiments
from result_schema import export_bundle


def experiment(x, y, *, unit_x="s", unit_y="V", name="data.csv"):
    return {"frame": pd.DataFrame({"x": x, "y": y}), "x": "x", "y": "y", "unit_x": unit_x,
            "unit_y": unit_y, "name": name, "sha256": "a" * 64}


def test_finite_pairs_are_separate_and_summary_is_reproducible():
    a = experiment([0, 1, 2, 3], [1, 3, np.nan, 7])
    b = experiment([0, 1, 2, 3], [2, 4, 6, 8])
    original = copy.deepcopy(a["frame"])
    summary, points = compare_experiments(a, b, confirmed=True)
    assert summary["status"] == "user_confirmed_not_independently_verified"
    assert summary["datasets"][0]["valid_pairs"] == 3
    assert summary["datasets"][0]["excluded_pairs"] == 1
    assert summary["datasets"][0]["mean_y"] == pytest.approx(11 / 3)
    assert summary["mean_y_difference_second_minus_first"] == pytest.approx(5 - 11 / 3)
    assert points.groupby("dataset").size().tolist() == [3, 4]
    assert "not establish causation" in summary["limitations"]
    pd.testing.assert_frame_equal(a["frame"], original)


@pytest.mark.parametrize("first,second,confirmed", [
    (experiment([1, 2], [3, 4]), experiment([1, 2], [3, 4]), False),
    (experiment([1, 2], [3, 4], unit_x=""), experiment([1, 2], [3, 4]), True),
    (experiment([1, 2], [3, 4]), experiment([1, 2], [3, 4], unit_y="mV"), True),
    (experiment([1, 2], [3, 4]), experiment([1, 2], [float("nan"), 4]), True),
])
def test_incompatible_or_insufficient_input_is_rejected(first, second, confirmed):
    with pytest.raises(ValueError):
        compare_experiments(first, second, confirmed=confirmed)


def test_plot_is_capped_without_truncating_computed_statistics():
    n = MAX_COMPARISON_POINTS + 25
    a = experiment(np.arange(n), np.arange(n))
    summary, points = compare_experiments(a, a, confirmed=True)
    assert summary["datasets"][0]["valid_pairs"] == n
    assert summary["datasets"][0]["mean_y"] == pytest.approx((n - 1) / 2)
    assert len(points) == 2 * MAX_COMPARISON_POINTS


def test_export_includes_summary_not_raw_rows_and_escapes_names():
    a, b = experiment([0, 1], [1, 2], name="<img src=x>.csv"), experiment([0, 1], [3, 4])
    summary, _ = compare_experiments(a, b, confirmed=True)
    result = {"comparison": summary}
    exported = export_bundle(result)
    stored = json.loads(exported["results.json"])
    assert stored["comparison"] == summary
    report = exported["report.md"].decode()
    assert "Experiment comparison" in report and "<img" not in report
    assert "not independently verified" in report
    assert "frame" not in stored["comparison"]["datasets"][0]


def test_ui_requires_confirmation_and_reconfirms_on_new_upload(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    upload = next(w for w in at.file_uploader if w.label == "Second experiment CSV")
    upload.set_value(("comparison.csv", b"current,voltage\n0,1\n1,2\n2,3\n3,4\n", "text/csv")).run()
    assert not at.exception and not at.error
    next(w for w in at.text_input if w.label == "Second experiment X unit").set_value("A")
    next(w for w in at.text_input if w.label == "Second experiment Y unit").set_value("V")
    at.run()
    checkbox = next(w for w in at.checkbox if w.label.startswith("I confirm the mapped quantities"))
    assert not checkbox.value
    checkbox.check().run()
    assert not at.exception and not at.error
    assert any("Difference in paired Y means" in text.value for text in at.text)
    assert any("Experiment comparison" in text.value for text in at.code)
    assert len(at.get("download_button")) == 3
    upload = next(w for w in at.file_uploader if w.label == "Second experiment CSV")
    upload.set_value(("comparison.csv", b"current,voltage\n0,4\n1,5\n2,6\n3,7\n", "text/csv")).run()
    checkbox = next(w for w in at.checkbox if w.label.startswith("I confirm the mapped quantities"))
    assert not checkbox.value
    assert not any("Difference in paired Y means" in text.value for text in at.text)
