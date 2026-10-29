"""Inspectable, analysis-bound evidence for deterministic insight paths.

This ledger stores summaries and selected settings, not raw observations or AI
prose. Evidence presence is not proof that an interpretation is scientifically
valid. Optional report sections are included only when they exist.
"""
from __future__ import annotations

import hashlib
import json


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _resolve(result, path):
    value = result
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def build_evidence_ledger(result: dict) -> dict:
    """Create IDs tied to the primary analysis and actual path/value pairs.

    Missing or null paths are explicitly reported, not treated as evidence.
    Analysis fingerprints exclude AI, report time and optional late UI panels.
    """
    foundational = {key: result.get(key) for key in (
        "source", "roles", "cleaning", "statistics", "correlation", "outliers", "fit", "domain", "uncertainty"
    )}
    fingerprint = hashlib.sha256(_canonical(foundational).encode("utf-8")).hexdigest()
    insights = (result.get("insights") or {}).get("items") or []
    paths = {path for card in insights for path in (card.get("evidence_paths") or [])}
    paths.update(("source.sha256", "roles.x", "roles.y", "fit.model", "fit.success"))
    for path in ("comparison.mean_y_difference_second_minus_first", "comparison.datasets", "comparison.difference_interval",
                 "uncertainty.parameters", "predictions.intervals", "research.chapter.derived",
                 "correlated_propagation", "monte_carlo_propagation", "theory_validation"):
        if _resolve(result, path)[0]:
            paths.add(path)
    source = result.get("source") or {}
    fit = result.get("fit") or {}
    items, missing, by_path = [], [], {}
    for path in sorted(paths):
        exists, value = _resolve(result, path)
        if not exists or value is None:
            missing.append(path)
            continue
        digest = hashlib.sha256(_canonical([path, value]).encode("utf-8")).hexdigest()[:12]
        identifier = f"ev-{fingerprint[:12]}-{digest}"
        kind = ("user_supplied_metadata" if path.startswith("roles.") else
                "source_provenance" if path.startswith("source.") else
                "statistical_estimate" if path.startswith(("uncertainty.", "predictions.", "correlated_propagation", "monte_carlo_propagation")) else
                "derived_result")
        item = {"id": identifier, "type": kind, "result_path": path, "value": value,
                "source_sha256": source.get("sha256"),
                "source_kind": source.get("data_origin", "not_independently_verified"),
                "method": fit.get("model") if path.startswith(("fit.", "uncertainty.", "predictions.")) else None,
                "assumptions": fit.get("assumptions") if path.startswith("fit.") else None}
        items.append(item)
        by_path[path] = identifier
    links = [{"insight_id": card.get("id"),
              "evidence_ids": [by_path[p] for p in card.get("evidence_paths", []) if p in by_path],
              "missing_paths": [p for p in card.get("evidence_paths", []) if p not in by_path]}
             for card in insights]
    return {"version": "1.0", "analysis_fingerprint": fingerprint, "items": items,
            "insight_links": links, "unavailable_paths": missing,
            "limitations": "Links verify the presence of local values, not causal, semantic, scientific or AI-claim correctness."}
