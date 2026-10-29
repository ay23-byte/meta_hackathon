"""Conservative checks on explicit AI numerical assertions.

This is not a semantic entailment checker: only a small set of explicit
metric=value patterns is compared, and everything else remains unverified.
"""
from __future__ import annotations

import math
import re

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_PATTERNS = {
    "slope": re.compile(rf"\bslope\s*(?:=|:|\bis\b)\s*({_NUMBER})", re.I),
    "intercept": re.compile(rf"\bintercept\s*(?:=|:|\bis\b)\s*({_NUMBER})", re.I),
    "rmse": re.compile(rf"\brmse\s*(?:=|:|\bis\b)\s*({_NUMBER})", re.I),
    "r2": re.compile(rf"\br(?:²|2|\^2)\s*(?:=|:|\bis\b)\s*({_NUMBER})", re.I),
    "n": re.compile(rf"\bn\s*(?:=|:)\s*({_NUMBER})", re.I),
}


def check_report_numbers(structured: dict, context: dict) -> dict:
    """Flag contradictions in supported explicit patterns; never infer entailment.

    References are checked against the actual sent context. A number with no
    authoritative value, unsupported wording, unit, citation, or scientific
    interpretation is not verified. Comparisons allow modest rounding.
    """
    fit = context.get("fit") or {}
    parameters, metrics = fit.get("parameters") or {}, fit.get("metrics") or {}
    expected = {"slope": parameters.get("slope"), "intercept": parameters.get("intercept"),
                "rmse": metrics.get("rmse"), "r2": metrics.get("r2"), "n": fit.get("n_observations")}
    allowed = set(context.get("result_ids") or [])
    checked, contradictions, unverified = [], [], []
    texts = [(f"section:{item.get('title', '')}", item.get("content", ""))
             for item in structured.get("sections", []) if isinstance(item, dict)]
    for i, claim in enumerate(structured.get("claims", []), 1):
        if not isinstance(claim, dict):
            continue
        name = f"claim:{i}"
        texts.append((name, claim.get("claim", "")))
        ids = claim.get("evidence_ids") or []
        if "result_ids" not in context:
            unverified.append(f"{name}: this legacy context has no evidence-ID registry")
        elif not ids or any(identifier not in allowed for identifier in ids):
            contradictions.append({"location": name, "reason": "Missing or unknown evidence identifier."})
        # Presence of an ID does not establish semantic support.
        unverified.append(f"{name}: evidence-to-claim meaning and units require human review")
    for location, text in texts:
        if not isinstance(text, str):
            continue
        for name, pattern in _PATTERNS.items():
            for match in pattern.finditer(text):
                observed = float(match.group(1))
                reference = expected.get(name)
                if (not isinstance(reference, (int, float)) or isinstance(reference, bool)
                        or not math.isfinite(reference) or not math.isfinite(observed)):
                    unverified.append(f"{location}: {name} has no comparable finite result")
                elif not math.isclose(observed, reference, rel_tol=5e-4, abs_tol=0.0):
                    contradictions.append({"location": location, "metric": name,
                                           "reason": "Explicit number conflicts with the current computed fit."})
                else:
                    checked.append({"location": location, "metric": name})
    return {"status": "contradiction" if contradictions else "partially_checked",
            "checked": checked, "contradictions": contradictions, "unverified": unverified,
            "limitations": "Only explicit slope, intercept, R², RMSE and n patterns are checked with rounding tolerance. "
                           "Units, citations, other numbers, causal claims and semantic evidence support are not verified."}
