"""Previewable, consent-driven cleaning for arbitrary tabular datasets.

The raw uploaded frame is never mutated. Invalid and missing values are
tracked separately, and no row is discarded unless the user opts in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from column_inference import ColumnProfile
from data_io import NumericCoercion, coerce_numeric


@dataclass
class CleaningPlan:
    remove_duplicates: bool = False
    exclude_invalid_pairs: bool = True
    numeric_columns: tuple[str, ...] = ()
    pair_columns: tuple[str, ...] = ()


@dataclass
class ColumnCleaning:
    name: str
    n_missing: int
    n_invalid: int
    n_nonfinite: int
    n_coerced: int
    n_valid: int


@dataclass
class CleaningReport:
    n_rows_in: int
    n_rows_out: int
    n_duplicates_removed: int = 0
    n_invalid_pair_rows: int = 0
    n_cells_changed: int = 0
    per_column: list[ColumnCleaning] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rows_in": self.n_rows_in,
            "rows_out": self.n_rows_out,
            "duplicates_removed": self.n_duplicates_removed,
            "invalid_pair_rows_excluded": self.n_invalid_pair_rows,
            "cells_coerced_to_numeric": self.n_cells_changed,
            "columns": [
                {
                    "name": column.name,
                    "missing": column.n_missing,
                    "invalid": column.n_invalid,
                    "nonfinite": column.n_nonfinite,
                    "coerced": column.n_coerced,
                    "valid": column.n_valid,
                }
                for column in self.per_column
            ],
            "notes": list(self.notes),
        }


@dataclass
class CleaningResult:
    working: pd.DataFrame
    report: CleaningReport
    numeric: dict[str, NumericCoercion]
    valid_pair_mask: np.ndarray

    def usable_pairs(self, x: str, y: str) -> np.ndarray:
        if x not in self.numeric or y not in self.numeric:
            return np.zeros(len(self.working), dtype=bool)
        return self.numeric[x].usable & self.numeric[y].usable


def _coerce_frame(frame: pd.DataFrame, columns: tuple[str, ...]) -> tuple[pd.DataFrame, dict[str, NumericCoercion], int]:
    working = frame.copy()
    coercions: dict[str, NumericCoercion] = {}
    changed = 0
    for name in columns:
        if name not in working.columns:
            continue
        coerce = coerce_numeric(working[name])
        coercions[name] = coerce
        original = working[name].astype("object")
        # Preserve the raw column; add a numeric companion column.
        numeric_name = f"__numeric__{name}"
        working[numeric_name] = coerce.values
        changed += int(
            sum(
                1
                for before, after in zip(original, working[numeric_name], strict=False)
                if str(before) != str(after) and not (pd.isna(before) and pd.isna(after))
            )
        )
    return working, coercions, changed


def build_plan(
    profiles: list[ColumnProfile],
    *,
    remove_duplicates: bool = False,
    exclude_invalid_pairs: bool = True,
    x: str | None = None,
    y: str | None = None,
    extra_numeric: tuple[str, ...] = (),
) -> CleaningPlan:
    numbers = tuple(dict.fromkeys(
        [profile.name for profile in profiles if profile.is_numeric]
        + [name for name in extra_numeric if name]
    ))
    pair = tuple(name for name in (x, y) if name)
    return CleaningPlan(
        remove_duplicates=remove_duplicates,
        exclude_invalid_pairs=exclude_invalid_pairs,
        numeric_columns=numbers,
        pair_columns=pair,
    )


def preview_cleaning(frame: pd.DataFrame, plan: CleaningPlan) -> CleaningReport:
    """Compute exactly what would change, without modifying the input."""
    report = CleaningReport(n_rows_in=len(frame), n_rows_out=len(frame))
    for name in plan.numeric_columns:
        if name not in frame.columns:
            continue
        coerce = coerce_numeric(frame[name])
        report.per_column.append(
            ColumnCleaning(
                name=name,
                n_missing=int(coerce.missing.sum()),
                n_invalid=int(coerce.invalid.sum()),
                n_nonfinite=int(coerce.nonfinite.sum()),
                n_coerced=coerce.n_valid,
                n_valid=coerce.n_valid,
            )
        )
        report.n_cells_changed += coerce.n_valid
    if plan.remove_duplicates:
        report.n_duplicates_removed = int(frame.duplicated().sum())
    if plan.exclude_invalid_pairs and plan.pair_columns:
        masks = [
            coerce_numeric(frame[name]).usable
            for name in plan.pair_columns
            if name in frame.columns
        ]
        if masks:
            report.n_invalid_pair_rows = int((~np.logical_and.reduce(masks)).sum())

    # Invalid pairs are excluded from the *analysis view*, never deleted from
    # the cleaned dataset. Only explicit duplicate removal changes row count.
    report.n_rows_out = max(len(frame) - report.n_duplicates_removed, 0)
    report.notes.append(
        "Invalid non-blank values are distinct from missing observations. "
        "Neither is converted to zero."
    )
    report.notes.append(
        f"{report.n_invalid_pair_rows} row(s) lack a complete finite selected pair "
        "and are excluded from fitting, but remain in the cleaned CSV."
    )
    if not plan.remove_duplicates:
        report.notes.append("Duplicate rows are retained (removal is opt-in).")
    return report


def apply_cleaning(frame: pd.DataFrame, plan: CleaningPlan) -> CleaningResult:
    """Apply a plan to a copy of the frame and report every change."""
    working = frame.copy()
    report = preview_cleaning(frame, plan)

    if plan.remove_duplicates:
        working = working.loc[~working.duplicated()].reset_index(drop=True)

    working, coercions, _ = _coerce_frame(working, plan.numeric_columns)

    if plan.exclude_invalid_pairs and plan.pair_columns:
        masks = [coercions[name].usable for name in plan.pair_columns if name in coercions]
        valid_pair_mask = np.logical_and.reduce(masks) if masks else np.ones(len(working), dtype=bool)
    else:
        valid_pair_mask = np.ones(len(working), dtype=bool)

    # Recompute per-column counts on the post-deduplication working frame so
    # the report always matches what the analysis will actually see.
    report.per_column = [
        ColumnCleaning(
            name=name,
            n_missing=int(coerce.missing.sum()),
            n_invalid=int(coerce.invalid.sum()),
            n_nonfinite=int(coerce.nonfinite.sum()),
            n_coerced=coerce.n_valid,
            n_valid=coerce.n_valid,
        )
        for name, coerce in coercions.items()
    ]
    report.n_invalid_pair_rows = int((~valid_pair_mask).sum())
    report.n_cells_changed = sum(column.n_coerced for column in report.per_column)
    report.n_rows_out = len(working)
    return CleaningResult(
        working=working,
        report=report,
        numeric=coercions,
        valid_pair_mask=valid_pair_mask,
    )


def paired_values(result: CleaningResult, x: str, y: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return aligned finite x/y arrays plus the source row numbers."""
    if x not in result.numeric or y not in result.numeric:
        raise ValueError("Both selected columns must be numeric.")
    mask = result.usable_pairs(x, y)
    frame = result.working
    return (
        frame[f"__numeric__{x}"].to_numpy(dtype=float)[mask],
        frame[f"__numeric__{y}"].to_numpy(dtype=float)[mask],
        np.arange(1, len(frame) + 1)[mask],
    )
