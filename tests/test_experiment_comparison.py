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


def test_welch_interval_matches_independent_scipy_reference():
    from scipy.stats import t

    from experiment_comparison import independent_mean_difference_interval

    a = experiment([1, 2, 3, 4], [1, 2, 4, 5])
    b = experiment([1, 2, 3, 4, 5], [3, 4, 6, 7, 9])
    result = independent_mean_difference_interval(a, b, confirmed=True)
    ya = np.array([1, 2, 4, 5])
    yb = np.array([3, 4, 6, 7, 9])
    va, vb = np.var(ya, ddof=1)/len(ya), np.var(yb, ddof=1)/len(yb)
    df = (va + vb)**2 / (va**2/(len(ya)-1) + vb**2/(len(yb)-1))
    mean_difference = np.mean(yb) - np.mean(ya)
    margin = t.ppf(.975, df) * np.sqrt(va+vb)
    assert result["difference_second_minus_first"] == pytest.approx(mean_difference)
    assert result["lower"] == pytest.approx(mean_difference-margin)
    assert result["upper"] == pytest.approx(mean_difference+margin)
    assert "does not establish causation" in result["limitations"]


def test_welch_rejects_unconfirmed_incompatible_and_zero_variance():
    from experiment_comparison import independent_mean_difference_interval

    a = experiment([1, 2], [3, 3])
    b = experiment([1, 2], [4, 4])
    with pytest.raises(ValueError):
        independent_mean_difference_interval(a, b, confirmed=False)
    with pytest.raises(ValueError, match="variance"):
        independent_mean_difference_interval(a, b, confirmed=True)
    with pytest.raises(ValueError, match="Units"):
        independent_mean_difference_interval(a, experiment([1, 2], [4, 5], unit_y="mV"), confirmed=True)


def test_welch_is_separately_opt_in_and_exported(monkeypatch):
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(w for w in app.file_uploader if w.label == "Second experiment CSV").set_value(
        ("comparison.csv", b"current,voltage\n0,1\n1,2\n2,5\n3,6\n", "text/csv")).run()
    next(w for w in app.text_input if w.label == "Second experiment X unit").set_value("A")
    next(w for w in app.text_input if w.label == "Second experiment Y unit").set_value("V")
    app.run()
    next(w for w in app.checkbox if w.label.startswith("I confirm the mapped quantities")).check().run()
    inference = next(w for w in app.checkbox if w.label.startswith("Assume independent observations"))
    assert not inference.value
    inference.check().run()
    assert not app.exception and not app.error
    assert any("Conditional 95% mean-difference interval" in t.value for t in app.text)
    assert any("Welch mean-difference interval" in c.value for c in app.code)


def test_separate_linear_fits_and_export():
    from evidence_trace import build_evidence_ledger
    from experiment_comparison import compare_linear_fits

    first = experiment([0, 1, 2, 3], [1, 3, 5, 7])
    second = experiment([0, 1, 2, 3, 4], [2, 5, 8, 11, 14])
    comparison, _ = compare_experiments(first, second, confirmed=True)
    comparison["linear_fits"] = compare_linear_fits(first, second, confirmed=True)
    fit = comparison["linear_fits"]
    assert fit["fits"][0]["parameters"]["slope"] == pytest.approx(2)
    assert fit["fits"][1]["parameters"]["intercept"] == pytest.approx(2)
    assert fit["slope_difference_second_minus_first"] == pytest.approx(1)
    assert fit["slope_ratio_second_over_first"] == pytest.approx(1.5)
    assert any("different numbers" in warning for warning in fit["warnings"])
    result = {"comparison": comparison}
    result["evidence_ledger"] = build_evidence_ledger(result)
    files = export_bundle(result)
    assert "Separate unweighted linear fits" in files["report.md"].decode()
    assert any(item["result_path"] == "comparison.linear_fits" for item in result["evidence_ledger"]["items"])


def test_linear_comparison_handles_zero_slope_and_bad_mapping():
    from experiment_comparison import compare_linear_fits

    a = experiment([0, 1, 2], [1, 1, 1])
    b = experiment([0, 1, 2], [1, 2, 3])
    assert compare_linear_fits(a, b, confirmed=True)["slope_ratio_second_over_first"] is None
    b["x"] = "absent"
    with pytest.raises(ValueError):
        compare_linear_fits(a, b, confirmed=True)
    with pytest.raises(ValueError):
        compare_linear_fits(a, a, confirmed=False)


def test_separate_fit_ui_is_opt_in_and_reported(monkeypatch):
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=180).run()
    next(w for w in app.file_uploader if w.label == "Second experiment CSV").set_value(
        ("second.csv", b"current,voltage\n0,1\n1,3\n2,5\n3,7\n", "text/csv")).run()
    next(w for w in app.text_input if w.label == "Second experiment X unit").set_value("A")
    next(w for w in app.text_input if w.label == "Second experiment Y unit").set_value("V")
    app.run()
    next(w for w in app.checkbox if w.label.startswith("I confirm the mapped quantities")).check().run()
    toggle = next(w for w in app.checkbox if w.label.startswith("Fit separate unweighted lines"))
    assert not toggle.value
    toggle.check().run()
    assert not app.exception and not app.error
    assert any("Separate unweighted linear fits" in c.value for c in app.code)


def test_synthetic_ohmic_demo_known_fit_and_theory():
    from experiment_comparison import compare_linear_fits
    from theory_engine import validate_ohmic_prediction

    demo = Path(__file__).resolve().parents[1] / "data" / "demo"
    a = pd.read_csv(demo / "synthetic_ohmic_a.csv")
    b = pd.read_csv(demo / "synthetic_ohmic_b.csv")
    def item(frame):
        return {"frame": frame, "x": "current_A", "y": "voltage_V", "unit_x": "A", "unit_y": "V"}
    result = compare_linear_fits(item(a), item(b), confirmed=True)
    assert result["fits"][0]["parameters"]["slope"] == pytest.approx(9.98857142857143)
    assert result["fits"][1]["parameters"]["slope"] == pytest.approx(10.26)
    theory = validate_ohmic_prediction(a.current_A, a.voltage_V, unit_x="A", unit_y="V", resistance_ohm=10, confirmed=True)
    assert theory["pairs_used"] == 6 and theory["rmse"] == pytest.approx(0.0141421356237)
