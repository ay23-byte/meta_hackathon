"""Cleaning is previewable, non-destructive and never invents zero values."""

import numpy as np
import pandas as pd
import pytest

from cleaning import apply_cleaning, build_plan, paired_values, preview_cleaning
from column_inference import infer_columns


@pytest.fixture
def messy():
    return pd.DataFrame({
        "x": ["1", "2", "", "oops", "5", "inf", "7"],
        "y": ["2", "4", "6", "8", "NaN", "12", "14"],
        "label": ["a", "a", "b", "b", "c", "c", "d"],
    })


def test_preview_reports_missing_invalid_and_nonfinite_separately(messy):
    plan = build_plan(infer_columns(messy), x="x", y="y")
    report = preview_cleaning(messy, plan).as_dict()
    x_row = next(row for row in report["columns"] if row["name"] == "x")
    assert x_row["missing"] == 1       # empty string
    assert x_row["invalid"] == 1       # 'oops'
    assert x_row["nonfinite"] == 1     # 'inf'
    assert x_row["valid"] == 4
    assert report["rows_in"] == report["rows_out"] == 7
    assert report["invalid_pair_rows_excluded"] == 4
    assert any("converted to zero" in note for note in report["notes"])


def test_apply_keeps_raw_columns_and_adds_numeric_companions(messy):
    plan = build_plan(infer_columns(messy), x="x", y="y")
    result = apply_cleaning(messy, plan)
    assert list(result.working["x"]) == list(messy["x"])
    assert "__numeric__x" in result.working.columns
    assert np.isnan(result.working["__numeric__x"].iloc[3])
    assert result.working["__numeric__x"].iloc[3] != 0
    assert result.report.n_invalid_pair_rows == 4


def test_invalid_rows_remain_in_cleaned_csv_but_not_in_fitted_pairs(messy):
    plan = build_plan(infer_columns(messy), x="x", y="y")
    result = apply_cleaning(messy, plan)
    x, y, rows = paired_values(result, "x", "y")
    assert len(result.working) == 7
    assert x.tolist() == [1.0, 2.0, 7.0]
    assert len(x) == len(y) == len(rows)
    assert all(np.isfinite(x)) and all(np.isfinite(y))
    assert 4 not in rows


def test_duplicate_removal_is_opt_in(messy):
    with_dupes = pd.concat([messy, messy.iloc[[0]]], ignore_index=True)
    profiles = infer_columns(with_dupes)
    off = apply_cleaning(with_dupes, build_plan(profiles, x="x", y="y"))
    on = apply_cleaning(with_dupes, build_plan(profiles, remove_duplicates=True, x="x", y="y"))
    assert off.report.n_duplicates_removed == 0
    assert on.report.n_duplicates_removed == 1
    assert len(on.working) == len(with_dupes) - 1


def test_consent_off_keeps_all_rows_but_fitting_still_requires_finite_pairs(messy):
    plan = build_plan(infer_columns(messy), exclude_invalid_pairs=False, x="x", y="y")
    result = apply_cleaning(messy, plan)
    assert result.valid_pair_mask.all()
    x, y, _ = paired_values(result, "x", "y")
    assert np.all(np.isfinite(x)) and np.all(np.isfinite(y))


def test_paired_values_rejects_non_numeric_selection(messy):
    plan = build_plan(infer_columns(messy), x="x", y="y")
    result = apply_cleaning(messy, plan)
    with pytest.raises(ValueError, match="numeric"):
        paired_values(result, "label", "y")


def test_extra_numeric_overrides_allow_mixed_text_columns():
    frame = pd.DataFrame({"alpha": ["1", "2", "3"], "beta": ["mostly text", "4", "5"]})
    plan = build_plan(infer_columns(frame), x="alpha", y="beta", extra_numeric=("beta",))
    result = apply_cleaning(frame, plan)
    x, y, _ = paired_values(result, "alpha", "beta")
    assert len(x) == len(y) == 2
