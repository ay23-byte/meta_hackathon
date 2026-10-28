"""Robust, dependency-light CSV import for arbitrary experimental datasets.

The loader never mutates the uploaded bytes and never converts a failed
numeric parse into zero. It records enough metadata (delimiter, encoding,
SHA-256, duplicate headers) to make any analysis reproducible.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_ROWS = 200_000
ALLOWED_SUFFIXES = frozenset({".csv", ".tsv", ".txt"})

# latin-1 is last: it decodes any byte sequence, but can silently mojibake.
ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
DELIMITERS = ",;\t|"

# Tokens pandas treats as missing. Kept explicit so "invalid" means something.
MISSING_TOKENS = {"", "na", "n/a", "nan", "null", "none", "-", "--", "?"}


class DataImportError(ValueError):
    """User-facing import failure with a safe, actionable message."""


@dataclass
class DatasetLoad:
    frame: pd.DataFrame
    delimiter: str
    encoding: str
    original_bytes: bytes
    sha256: str
    source_name: str
    header_labels: list[str] = field(default_factory=list)
    duplicate_headers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return len(self.frame)

    @property
    def n_columns(self) -> int:
        return len(self.frame.columns)


@dataclass
class NumericCoercion:
    """Three-way classification of a column's raw values.

    ``missing`` = legitimately absent observation.
    ``invalid`` = present but unparseable text (never coerced to zero).
    ``nonfinite`` = parsed as a number but infinite.
    """

    values: np.ndarray
    missing: np.ndarray
    invalid: np.ndarray
    nonfinite: np.ndarray
    raw: pd.Series

    @property
    def usable(self) -> np.ndarray:
        return ~(self.missing | self.invalid | self.nonfinite)

    @property
    def parseable(self) -> np.ndarray:
        """Non-blank values that parsed as a number (including +/-inf)."""
        return ~(self.missing | self.invalid)

    @property
    def n_valid(self) -> int:
        return int(self.usable.sum())


def decode_bytes(raw: bytes, encodings=ENCODINGS) -> tuple[str, str, list[str]]:
    """Decode with the first encoding that works; warn about fallbacks."""
    warnings: list[str] = []
    candidates = list(encodings)
    # utf-8-sig is only meaningful (and only reported) when a BOM is present.
    if not raw.startswith(b"\xef\xbb\xbf"):
        candidates = [encoding for encoding in candidates if encoding != "utf-8-sig"]
    for encoding in candidates:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding not in ("utf-8", "utf-8-sig"):
            warnings.append(
                f"File is not UTF-8; decoded as {encoding}. "
                "Check that column names and text values look correct."
            )
        return text, encoding, warnings
    raise DataImportError("Could not decode the file with any supported text encoding.")


def sniff_delimiter(text: str, delimiters: str = DELIMITERS) -> str:
    """Detect a delimiter, falling back to a header-line frequency count."""
    sample = text[:8192]
    try:
        detected = csv.Sniffer().sniff(sample, delimiters=delimiters).delimiter
        if detected in delimiters:
            return detected
    except csv.Error:
        pass

    header = sample.splitlines()[0] if sample.splitlines() else ""
    counts = {d: header.count(d) for d in delimiters}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _header_labels(text: str, delimiter: str) -> list[str]:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    try:
        return next(csv.reader([first_line], delimiter=delimiter))
    except (csv.Error, StopIteration):
        return [first_line]


def _check_field_counts(text: str, delimiter: str) -> None:
    """Reject rows wider than the header before pandas can shift columns.

    With ``engine='python'`` pandas silently treats extra leading fields as an
    index when a data row has more fields than the header. That quietly moves
    every value by one column, which is unacceptable for scientific data.
    """
    import csv

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None)
    if not header:
        raise DataImportError("The CSV has no header row.")
    width = len(header)
    for line_number, row in enumerate(reader, start=2):
        if not row or all(not str(cell).strip() for cell in row):
            continue
        if len(row) > width:
            raise DataImportError(
                f"Row {line_number} has {len(row)} fields but the header has {width}. "
                "Check for an unquoted delimiter or a missing header entry."
            )


def _find_duplicate_headers(labels: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for label in labels:
        if label in seen and label not in duplicates:
            duplicates.append(label)
        seen.add(label)
    return duplicates


def read_csv_robust(
    file_object,
    *,
    source_name: str = "dataset.csv",
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> DatasetLoad:
    """Read a CSV-like file from bytes, a path, or a file-like object."""
    if isinstance(file_object, (bytes, bytearray)):
        raw = bytes(file_object)
    elif isinstance(file_object, (str, Path)):
        try:
            raw = Path(file_object).read_bytes()
        except OSError as exc:
            raise DataImportError(f"Could not read {source_name}: {exc}") from exc
    elif hasattr(file_object, "read"):
        try:
            position = file_object.tell()
            file_object.seek(0)
            raw = file_object.read()
            file_object.seek(position)
        except (OSError, ValueError, AttributeError) as exc:
            raise DataImportError(f"Could not read {source_name}: {exc}") from exc
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
    else:
        raise DataImportError("Unsupported file object; provide bytes, a path, or a file-like object.")

    if not raw or not raw.strip():
        raise DataImportError("The file is empty or contains only whitespace.")
    name = str(source_name)
    suffix = Path(name).suffix.casefold()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise DataImportError(
            f"Unsupported file extension '{suffix}' for {name}. "
            "Use a delimited .csv, .tsv or .txt file."
        )
    if len(raw) > max_bytes:
        raise DataImportError(
            f"The file has {len(raw):,} bytes, which exceeds the "
            f"{max_bytes:,}-byte limit. Upload a smaller file."
        )

    text, encoding, warnings = decode_bytes(raw)
    delimiter = sniff_delimiter(text)
    _check_field_counts(text, delimiter)
    duplicate_headers = _find_duplicate_headers(_header_labels(text, delimiter))
    if duplicate_headers:
        warnings.append(
            "Duplicate column names were found in the header "
            f"({', '.join(map(str, duplicate_headers))}). pandas renamed them "
            "with a numeric suffix; verify the correct column is selected."
        )

    try:
        frame = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=object,
            keep_default_na=False,
            na_values=list(MISSING_TOKENS),
            skip_blank_lines=True,
            engine="python",
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise DataImportError(f"Could not parse the CSV: {type(exc).__name__}: {exc}") from exc

    if frame.empty or len(frame.columns) == 0:
        raise DataImportError("The CSV contains no usable rows or columns.")
    if len(frame) > max_rows:
        raise DataImportError(
            f"The CSV has {len(frame):,} rows, which exceeds the "
            f"{max_rows:,}-row limit. Upload a smaller dataset."
        )

    # Strip surrounding whitespace from labels; keep originals for reporting.
    header_labels = [str(column) for column in frame.columns]
    cleaned_names = [re.sub(r"\s+", " ", name).strip() or f"column_{i}" for i, name in enumerate(header_labels)]
    if cleaned_names != header_labels:
        warnings.append("Column names were trimmed of extra whitespace.")
    if _find_duplicate_headers(cleaned_names):
        raise DataImportError("Column names become duplicates after whitespace normalization. "
                              "Rename the conflicting headers before uploading.")
    frame.columns = cleaned_names

    return DatasetLoad(
        frame=frame,
        delimiter=delimiter,
        encoding=encoding,
        original_bytes=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        source_name=name,
        header_labels=header_labels,
        duplicate_headers=duplicate_headers,
        warnings=warnings,
    )


def coerce_numeric(series: pd.Series) -> NumericCoercion:
    """Classify raw values as usable / missing / invalid / non-finite.

    A failed parse is recorded as ``invalid`` and becomes NaN in ``values``;
    it is never replaced by zero.
    """
    raw = series.astype("object")
    stripped = raw.map(lambda value: str(value).strip() if not pd.isna(value) else "")
    is_blank = stripped.str.casefold().isin(MISSING_TOKENS)
    parsed = pd.to_numeric(stripped, errors="coerce")
    values = parsed.to_numpy(dtype=float, na_value=np.nan)

    with np.errstate(invalid="ignore"):
        nonfinite = np.isinf(values)
    invalid = (~is_blank.to_numpy()) & np.isnan(values)
    missing = is_blank.to_numpy()

    values = np.where(nonfinite, np.nan, values)
    return NumericCoercion(
        values=values,
        missing=missing,
        invalid=invalid,
        nonfinite=nonfinite,
        raw=raw,
    )
