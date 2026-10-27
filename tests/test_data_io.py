"""Robust import: delimiters, encodings, raw headers and numeric coercion."""

import hashlib
import io

import numpy as np
import pandas as pd
import pytest

from data_io import (
    DataImportError,
    coerce_numeric,
    decode_bytes,
    read_csv_robust,
    sniff_delimiter,
)


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_delimiters_are_detected(delimiter):
    text = f"alpha{delimiter}beta\n1{delimiter}2\n3{delimiter}4\n"
    assert sniff_delimiter(text) == delimiter
    load = read_csv_robust(io.BytesIO(text.encode()), source_name="d.txt")
    assert load.delimiter == delimiter
    assert list(load.frame.columns) == ["alpha", "beta"]
    assert load.frame["beta"].tolist() == ["2", "4"]


def test_utf8_bom_is_reported_only_when_present():
    _, encoding, warnings = decode_bytes(b"a,b\n1,2\n")
    assert encoding == "utf-8" and not warnings
    bom, encoding, warnings = decode_bytes(b"\xef\xbb\xbfa,b\n1,2\n")
    assert encoding == "utf-8-sig" and bom.lstrip("\ufeff") == "a,b\n1,2\n"


def test_cp1252_fallback_warns_and_preserves_header():
    raw = "temperature_deg°C;pressure\n20;101\n".encode("cp1252")
    load = read_csv_robust(io.BytesIO(raw), source_name="cp.csv")
    assert load.encoding == "cp1252"
    assert any("not UTF-8" in warning for warning in load.warnings)
    assert "temperature_deg°C" in load.frame.columns


def test_duplicate_raw_headers_are_warned_about():
    load = read_csv_robust(b"U (V),U (V),I (A)\n1,2,3\n", source_name="dup.csv")
    assert load.duplicate_headers == ["U (V)"]
    assert "U (V).1" in load.frame.columns
    assert any("Duplicate column names" in warning for warning in load.warnings)


def test_missing_invalid_and_nonfinite_are_distinct():
    series = pd.Series(["1", "", "NA", "oops", "inf", "-inf", "2.5", "nan", None])
    result = coerce_numeric(series)
    assert result.n_valid == 2
    assert int(result.missing.sum()) == 4  # '', NA, nan, None
    assert int(result.invalid.sum()) == 1  # oops
    assert int(result.nonfinite.sum()) == 2  # inf, -inf
    assert result.values[0] == 1.0
    assert np.isnan(result.values[1]) and np.isnan(result.values[3])
    # Nothing is coerced to zero.
    assert 0.0 not in result.values[np.isfinite(result.values)]


def test_decimal_commas_are_reported_invalid_not_silently_converted():
    result = coerce_numeric(pd.Series(["1,5", "2,0"]))
    assert result.n_valid == 0
    assert int(result.invalid.sum()) == 2


def test_source_forms_and_hash():
    raw = b"x,y\n1,2\n3,4\n"
    from_bytes = read_csv_robust(raw, source_name="a.csv")
    from_buffer = read_csv_robust(io.BytesIO(raw), source_name="a.csv")
    assert from_bytes.sha256 == from_buffer.sha256 == hashlib.sha256(raw).hexdigest()
    assert from_bytes.n_rows == 2 and from_bytes.n_columns == 2


def test_bounds_and_empty_input_raise_data_import_error():
    with pytest.raises(DataImportError):
        read_csv_robust(b"", source_name="empty.csv")
    with pytest.raises(DataImportError, match="limit"):
        read_csv_robust(b"a,b\n1,2\n", source_name="big.csv", max_bytes=3)
    with pytest.raises(DataImportError, match="row"):
        read_csv_robust(b"a,b\n1,2\n3,4\n", source_name="rows.csv", max_rows=1)


def test_unquoted_ragged_rows_are_rejected_not_silently_repaired():
    with pytest.raises(DataImportError):
        read_csv_robust(b"a,b\n1,2,3\n4,5,6\n", source_name="ragged.csv")
