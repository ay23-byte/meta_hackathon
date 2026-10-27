"""Heuristic column classification and role suggestion.

Classifications are *suggestions* about data shape, never claims about
scientific meaning. The user always has the final say on which column is X,
Y, group, time, or uncertainty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from data_io import coerce_numeric

KIND_CONTINUOUS = "numeric_continuous"
KIND_INTEGER = "numeric_integer"
KIND_DATETIME = "datetime"
KIND_CATEGORICAL = "categorical"
KIND_IDENTIFIER = "text_identifier"
KIND_BOOLEAN = "boolean"
KIND_EMPTY = "empty"

ROLE_HINTS = {
    "x": {
        "time", "t", "times", "date", "datetime", "timestamp", "x", "independent",
        "concentration", "dose", "temperature", "temp", "current", "currenta", "i", "ia",
    },
    "y": {
        "y", "response", "dependent", "signal", "value", "measurement", "voltage",
        "voltagev", "v", "absorbance", "od600", "yield", "force", "pressure",
    },
    "group": {"group", "batch", "sample", "condition", "treatment", "category", "label", "type", "replicate"},
    "time": {"time", "t", "date", "datetime", "timestamp", "elapsed", "duration"},
    "uncertainty": {"error", "err", "uncertainty", "sigma", "std", "stdev", "sd", "se", "sem", "u", "dy"},
}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).casefold())


@dataclass
class ColumnProfile:
    name: str
    kind: str
    n_total: int
    n_valid: int
    n_missing: int
    n_invalid: int
    n_nonfinite: int
    n_unique: int
    is_integer: bool
    is_datetime: bool
    suggested_role: str | None = None
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    @property
    def is_numeric(self) -> bool:
        return self.kind in (KIND_CONTINUOUS, KIND_INTEGER)


@dataclass
class RoleSuggestion:
    x: str | None = None
    y: str | None = None
    group: str | None = None
    time: str | None = None
    uncertainty: str | None = None
    secondary_y: list[str] = field(default_factory=list)
    ambiguous: bool = False
    notes: list[str] = field(default_factory=list)


def classify_column(frame: pd.DataFrame, name: str) -> ColumnProfile:
    series = frame[name]
    n_total = len(series)
    raw_strings = series.map(
        lambda value: "" if pd.isna(value) else str(value).strip()
    )
    nonblank = raw_strings[raw_strings != ""]
    n_unique = int(nonblank.nunique())

    coerce = coerce_numeric(series)
    n_numeric_potential = int((coerce.usable).sum())
    n_parseable = int(coerce.parseable.sum())
    n_nonblank = int((~coerce.missing).sum())
    # Judge the column by its non-blank values: a single typo or an inf
    # should not turn a measurement column into a categorical one.
    numeric_ratio = n_parseable / max(n_nonblank, 1)

    reasons: list[str] = []
    is_datetime = False
    if numeric_ratio < 0.8 and len(nonblank) >= 2:
        try:
            parsed_dates = pd.to_datetime(nonblank, errors="coerce", format="mixed")
            is_datetime = bool(parsed_dates.notna().mean() >= 0.8 and nonblank.nunique() > 1)
        except (ValueError, TypeError):
            is_datetime = False

    is_numeric = numeric_ratio >= 0.6 and n_parseable >= 2
    if n_total == 0 or (n_numeric_potential == 0 and not len(nonblank)):
        kind = KIND_EMPTY
    elif is_numeric:
        usable_values = coerce.values[coerce.usable]
        with np.errstate(invalid="ignore"):
            is_integer = bool(
                usable_values.size and np.all(np.isfinite(usable_values))
                and np.allclose(usable_values, np.round(usable_values))
            )
        kind = KIND_INTEGER if is_integer else KIND_CONTINUOUS
    elif is_datetime:
        kind = KIND_DATETIME
    elif len(nonblank) and nonblank.str.casefold().isin({"true", "false", "yes", "no", "0", "1"}).all():
        kind = KIND_BOOLEAN
    elif n_unique <= min(10, max(2, n_total // 2)):
        # Scale the cardinality limit with the row count: four distinct
        # labels in four rows is an identifier, not a category.
        kind = KIND_CATEGORICAL
    else:
        kind = KIND_IDENTIFIER

    numeric_kind = kind in (KIND_CONTINUOUS, KIND_INTEGER)
    if is_numeric:
        reasons.append(f"{numeric_ratio:.0%} of non-blank values parse as numbers")
    elif is_datetime:
        reasons.append("most non-blank values parse as dates/timestamps")
    elif kind == KIND_CATEGORICAL:
        reasons.append(f"only {n_unique} distinct labels")
    if numeric_kind and coerce.invalid.any():
        reasons.append(f"{int(coerce.invalid.sum())} unparseable non-blank value(s)")

    return ColumnProfile(
        name=name,
        kind=kind,
        n_total=n_total,
        n_valid=n_numeric_potential if numeric_kind else len(nonblank),
        n_missing=int(coerce.missing.sum()),
        # "Invalid" means unparseable *as a number*; it is meaningless for a
        # legitimate text/category column.
        n_invalid=int(coerce.invalid.sum()) if numeric_kind else 0,
        n_nonfinite=int(coerce.nonfinite.sum()) if numeric_kind else 0,
        n_unique=n_unique,
        is_integer=kind == KIND_INTEGER,
        is_datetime=is_datetime,
        reasons=reasons,
        examples=[str(value)[:40] for value in nonblank.head(3).tolist()],
    )


def infer_columns(frame: pd.DataFrame) -> list[ColumnProfile]:
    return [classify_column(frame, name) for name in frame.columns]


def numeric_columns(profiles: list[ColumnProfile]) -> list[str]:
    return [profile.name for profile in profiles if profile.is_numeric]


def _hint_match(profile: ColumnProfile, role: str) -> float:
    normalized = _normalize(profile.name)
    hints = ROLE_HINTS[role]
    if normalized in hints:
        return 1.0
    return 0.6 if any(hint in normalized for hint in hints if len(hint) > 3) else 0.0


def suggest_roles(profiles: list[ColumnProfile]) -> RoleSuggestion:
    """Suggest roles from data shape and weak name hints; flag ambiguity."""
    suggestion = RoleSuggestion()
    numbers = [profile for profile in profiles if profile.is_numeric]
    datetimes = [profile for profile in profiles if profile.kind == KIND_DATETIME]
    categories = [profile for profile in profiles if profile.kind in (KIND_CATEGORICAL, KIND_BOOLEAN)]

    time_candidates = datetimes + [p for p in numbers if _hint_match(p, "time") > 0.9]
    if time_candidates:
        suggestion.time = max(time_candidates, key=_hint_score_time).name

    if numbers:
        scored = sorted(
            numbers,
            # Prefer more distinct values for X: a nearly constant column is
            # a poor independent variable even if its name contains a hint.
            key=lambda p: (_hint_match(p, "x"), p.n_valid, p.n_unique),
            reverse=True,
        )
        suggestion.x = scored[0].name
        y_candidates = [p for p in numbers if p.name != suggestion.x]
        if y_candidates:
            suggestion.y = max(y_candidates, key=lambda p: (_hint_match(p, "y"), p.n_valid)).name
            suggestion.secondary_y = [p.name for p in y_candidates if p.name != suggestion.y][:3]

    if categories:
        suggestion.group = max(categories, key=lambda p: (_hint_match(p, "group"), -p.n_unique)).name

    uncertainty_candidates = [p for p in numbers if _hint_match(p, "uncertainty") >= 0.6]
    if uncertainty_candidates:
        suggestion.uncertainty = max(uncertainty_candidates, key=lambda p: _hint_match(p, "uncertainty")).name

    if len(numbers) < 2:
        suggestion.ambiguous = True
        suggestion.notes.append(
            "Fewer than two numeric columns were detected. Select X and Y manually, "
            "or upload a dataset with at least two numeric measurements."
        )
    elif len(numbers) > 2:
        suggestion.ambiguous = True
        suggestion.notes.append(
            f"{len(numbers)} numeric columns were found. The suggested X/Y are a "
            "starting point; confirm which variables are independent and dependent."
        )
    if suggestion.time and suggestion.time == suggestion.x:
        suggestion.notes.append(
            f"'{suggestion.time}' looks like a time/date column. Use a time-series plot "
            "if the rows are ordered measurements."
        )
    if suggestion.uncertainty:
        suggestion.notes.append(
            f"'{suggestion.uncertainty}' may contain measurement uncertainties. "
            "Confirm the values and their units before using weighted fitting."
        )
    if not suggestion.notes:
        suggestion.notes.append(
            "Roles are inferred from data shape and weak name hints, not from "
            "scientific meaning. Confirm the selection before interpreting results."
        )
    return suggestion


def _hint_score_time(profile: ColumnProfile) -> float:
    return _hint_match(profile, "time") + (0.5 if profile.kind == KIND_DATETIME else 0.0)
