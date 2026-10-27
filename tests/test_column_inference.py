"""Column classification and role suggestions must not depend on fixed names."""

import numpy as np
import pandas as pd

from column_inference import (
    KIND_BOOLEAN,
    KIND_CATEGORICAL,
    KIND_CONTINUOUS,
    KIND_DATETIME,
    KIND_EMPTY,
    KIND_IDENTIFIER,
    KIND_INTEGER,
    classify_column,
    infer_columns,
    numeric_columns,
    suggest_roles,
)


def test_kinds_are_inferred_from_values_not_names():
    frame = pd.DataFrame({
        "zzz": [1.0, 2.5, 3.5, 4.0],
        "qqq": [1, 2, 3, 4],
        "www": [True, False, True, False],
        "rrr": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        "ttt": ["a", "b", "a", "b"],
        "uuu": ["id-1", "id-2", "id-3", "id-4"],
        "vvv": [None, None, None, None],
    })
    kinds = {p.name: p.kind for p in infer_columns(frame)}
    assert kinds["zzz"] == KIND_CONTINUOUS
    assert kinds["qqq"] == KIND_INTEGER
    assert kinds["www"] == KIND_BOOLEAN
    assert kinds["rrr"] == KIND_DATETIME
    assert kinds["ttt"] == KIND_CATEGORICAL
    assert kinds["uuu"] == KIND_IDENTIFIER
    assert kinds["vvv"] == KIND_EMPTY


def test_mixed_numeric_column_with_typo_is_still_numeric():
    profile = classify_column(pd.DataFrame({"m": ["1.0", "2.0", "oops", "4.0"]}), "m")
    assert profile.is_numeric
    assert profile.n_invalid == 1
    assert profile.n_valid == 3


def test_infinite_value_is_counted_not_dropped_silently():
    profile = classify_column(pd.DataFrame({"m": [1.0, 2.0, np.inf, 4.0]}), "m")
    assert profile.n_nonfinite == 1
    assert profile.n_valid == 3


def test_legitimate_text_column_has_no_invalid_count():
    profile = classify_column(pd.DataFrame({"label": ["alpha", "beta", "gamma", "delta"]}), "label")
    assert profile.n_invalid == 0
    assert not profile.is_numeric


def test_role_suggestions_work_for_unrelated_column_names():
    frame = pd.DataFrame({
        "frobnicator": np.linspace(0, 1, 8),
        "glorbometer": 2 * np.linspace(0, 1, 8) + 1,
        "cohort": ["x", "x", "y", "y"] * 2,
        "sigma_g": np.full(8, 0.1),
    })
    profiles = infer_columns(frame)
    roles = suggest_roles(profiles)
    assert set(numeric_columns(profiles)) == {"frobnicator", "glorbometer", "sigma_g"}
    assert roles.x in numeric_columns(profiles)
    assert roles.y in numeric_columns(profiles) and roles.y != roles.x
    assert roles.group == "cohort"
    assert roles.uncertainty == "sigma_g"
    assert roles.ambiguous  # three numeric columns


def test_single_numeric_column_is_flagged_ambiguous():
    roles = suggest_roles(infer_columns(pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})))
    assert roles.ambiguous
    assert roles.y is None
    assert any("manually" in note for note in roles.notes)
