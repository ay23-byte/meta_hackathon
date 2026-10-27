"""Input-validation and file-safety regressions for the delimited-text pipeline.

The supported contract remains CSV/TSV/TXT-like text with a header row. These
tests do not claim support for arbitrary scientific file formats.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

import cleaning
import column_inference
import data_io
from analysis_core import analyze_linear
from column_inference import infer_columns, suggest_roles
from data_io import DataImportError, coerce_numeric, read_csv_robust
from fitting_core import fit_linear


@pytest.mark.parametrize("raw", [b"", b"   \n\t\n  "])
def test_empty_or_whitespace_only_files_are_rejected(raw):
    with pytest.raises(DataImportError, match=r"empty|whitespace"):
        read_csv_robust(raw, source_name="empty.csv")


def test_header_only_file_is_rejected_with_clear_message():
    with pytest.raises(DataImportError, match="no usable rows or columns"):
        read_csv_robust(b"x,y\n", source_name="header_only.csv")


@pytest.mark.parametrize("name", ["data.xlsx", "data.json", "data.parquet", "data.dat"])
def test_unsupported_extensions_are_rejected(name):
    with pytest.raises(DataImportError, match="Unsupported file extension"):
        read_csv_robust(b"x,y\n1,2\n", source_name=name)


def test_ragged_rows_are_rejected_before_column_shift():
    with pytest.raises(DataImportError, match="fields but the header"):
        read_csv_robust(b"x,y\n1,2,3\n4,5\n", source_name="ragged.csv")


def test_non_utf8_encoding_fallback_is_explicit():
    raw = "temperature_deg°C;signal\n20;1.1\n".encode("cp1252")
    load = read_csv_robust(raw, source_name="cp1252.csv")
    assert load.encoding in ("cp1252", "latin-1")
    assert any("not UTF-8" in warning for warning in load.warnings)
    assert "temperature_deg°C" in load.frame.columns


def test_duplicate_headers_are_reported_not_silently_dropped():
    load = read_csv_robust(b"x,x,y\n1,2,3\n", source_name="dup.csv")
    assert load.duplicate_headers == ["x"]
    assert "x.1" in load.frame.columns
    assert any("Duplicate column names" in warning for warning in load.warnings)


def test_duplicate_rows_are_preserved_by_default():
    load = read_csv_robust(b"x,y\n1,2\n1,2\n3,4\n5,6\n", source_name="dup_rows.csv")
    assert load.n_rows == 4
    assert int(load.frame.duplicated().sum()) == 1


def test_mixed_numeric_text_missing_and_nonfinite_values_are_distinct():
    series = pd.Series(["1", "", "NA", "oops", "inf", "-inf", "2.5", "nan", None])
    result = coerce_numeric(series)
    assert result.n_valid == 2
    assert int(result.missing.sum()) == 4
    assert int(result.invalid.sum()) == 1
    assert int(result.nonfinite.sum()) == 2
    assert 0.0 not in result.values[np.isfinite(result.values)]


def test_uploaded_cells_are_data_not_code():
    # A formula-like cell is preserved as text; export escaping is tested
    # separately in tests/test_export_safety.py.
    load = read_csv_robust(b"x,note\n1,=cmd|'/c calc'!A1\n", source_name="cells.csv")
    assert load.frame["note"].iloc[0].startswith("=cmd|")
    for module in (data_io, cleaning, column_inference):
        source = inspect.getsource(module)
        for forbidden in ("eval(", "exec(", "compile(", "subprocess", "os.system", "__import__"):
            assert forbidden not in source


def test_extremely_large_finite_values_do_not_return_nan_success():
    x = np.arange(4, dtype=float)
    y = np.array([1e308, 1.1e308, 1.2e308, 1.3e308])
    fit = fit_linear(x, y)
    assert fit.success is False
    assert "non-finite" in fit.reason.casefold()


def test_insufficient_rows_and_missing_numeric_columns_are_actionable():
    assert fit_linear([1], [2]).success is False
    with pytest.raises(ValueError, match="At least two"):
        analyze_linear([1], [2])
    roles = suggest_roles(infer_columns(pd.DataFrame({
        "only_numeric": [1.0, 2.0, 3.0], "label": ["a", "b", "c"],
    })))
    assert roles.y is None
    assert any("Fewer than two numeric columns" in note for note in roles.notes)


def test_size_and_row_limits_are_enforced():
    with pytest.raises(DataImportError, match="byte limit"):
        read_csv_robust(b"x,y\n1,2\n", source_name="big.csv", max_bytes=3)
    with pytest.raises(DataImportError, match="row limit"):
        read_csv_robust(b"x,y\n1,2\n3,4\n", source_name="rows.csv", max_rows=1)


def test_source_name_without_extension_is_still_accepted_for_backward_compatibility():
    load = read_csv_robust(b"x,y\n1,2\n", source_name="dataset")
    assert load.n_rows == 1 and load.n_columns == 2


def test_traversal_like_source_name_is_only_metadata_not_a_file_path():
    # When bytes are supplied, source_name is provenance text only; it must
    # never be resolved as a path (temporary-file / path-traversal guard).
    load = read_csv_robust(b"x,y\n1,2\n", source_name="../../etc/passwd.csv")
    assert load.source_name == "../../etc/passwd.csv"
    assert load.n_rows == 1
    assert b"root:" not in load.original_bytes
