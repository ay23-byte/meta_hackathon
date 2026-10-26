"""Unit tests for the dashboard's pure helper functions."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import ask_muse
from app import (
    create_analysis_record,
    json_safe,
    make_context_hash,
    md_inline,
    safe_unit,
    validate_ai_report,
    validated_ai_structure,
)

ROOT = Path(__file__).resolve().parents[1]


def sample_record():
    frame = pd.read_csv(ROOT / "data" / "sample_voltage_current.csv")
    from analysis_core import analyze_linear, prepare_analysis_data

    prepared = prepare_analysis_data(frame, "current_A", "voltage_V")
    analysis = analyze_linear(prepared["current"], prepared["voltage"])
    return create_analysis_record(
        source="sample_voltage_current.csv",
        source_hash="a" * 64,
        current_col="current_A",
        voltage_col="voltage_V",
        current_unit="A",
        voltage_unit="V",
        question="How does voltage vary with current?",
        description=None,
        prepared=prepared,
        analysis=analysis,
    )


def valid_wrapper():
    return {
        "model": "meta-models/muse-spark-open",
        "structured": {
            "sections": [
                {"title": title, "content": "A short evidence note."}
                for title in ask_muse.REQUIRED_TITLES
            ],
            "claims": [],
        },
    }


def test_safe_unit_blocks_csv_formula_injection():
    assert safe_unit("A", "A") == "A"
    assert safe_unit("  mA ", "A") == "mA"
    assert safe_unit("", "A") == "A"
    assert safe_unit(None, "V") == "V"

    for payload in ("=1+1", "+SUM(A1)", "-2", "@cmd"):
        result = safe_unit(payload, "unit")
        # Dangerous leading characters are either stripped or neutralised
        # with a leading apostrophe; neither can start a spreadsheet formula.
        assert not result.startswith(("=", "+", "-", "@"))
        assert "=" not in result and "@" not in result

    assert safe_unit("-2", "unit") == "'-2"

    assert "<script>" not in safe_unit("A<script>alert(1)</script>", "A")
    assert len(safe_unit("x" * 200, "A")) <= 24


def test_md_inline_collapses_newlines_and_escapes_markdown():
    assert md_inline("hello\nworld") == "hello world"
    assert md_inline("a|b`c") == "a\\|b'c"
    assert len(md_inline("x" * 500)) <= 300


def test_json_safe_converts_numpy_and_non_finite_values():
    value = json_safe(
        {
            "integer": np.int64(4),
            "float": np.float64(1.5),
            "nan": float("nan"),
            "inf": float("inf"),
            "array": np.array([1.0, 2.0]),
            "flag": np.bool_(True),
        }
    )
    assert value["integer"] == 4
    assert value["flag"] is True
    assert value["nan"] is None
    assert value["inf"] is None
    assert value["array"] == [1.0, 2.0]
    # Strict JSON: no NaN/Infinity tokens can be emitted.
    assert "NaN" not in json.dumps(value, allow_nan=False)


def test_validate_ai_report_uses_the_provider_schema_limits():
    good = valid_wrapper()
    assert validate_ai_report(good) is True

    too_many_words = json.loads(json.dumps(good))
    too_many_words["structured"]["sections"][0]["content"] = "word " * 30
    assert validate_ai_report(too_many_words) is False

    oversized = json.loads(json.dumps(good))
    oversized["structured"]["sections"][0]["content"] = "x" * 1000
    assert validate_ai_report(oversized) is False

    wrong_title = json.loads(json.dumps(good))
    wrong_title["structured"]["sections"][0]["title"] = "Invented Section"
    assert validate_ai_report(wrong_title) is False

    too_many_claims = json.loads(json.dumps(good))
    too_many_claims["structured"]["claims"] = [
        {
            "claim": "c",
            "evidence": "e",
            "evidence_type": "t",
            "confidence_or_uncertainty": "u",
            "limitation": "l",
            "proposed_verification": "v",
        }
    ] * 3
    assert validate_ai_report(too_many_claims) is False

    assert validate_ai_report({"structured": good["structured"]}) is False
    assert validate_ai_report(None) is False
    assert validate_ai_report("a string") is False


def test_validated_ai_structure_sanitizes_provider_output():
    wrapper = valid_wrapper()
    wrapper["structured"]["extra"] = "untrusted"
    wrapper["structured"]["sections"][0]["extra"] = "untrusted"

    structure = validated_ai_structure(wrapper)

    assert structure is not None
    assert "extra" not in structure
    assert "extra" not in structure["sections"][0]
    assert [s["title"] for s in structure["sections"]] == list(
        ask_muse.REQUIRED_TITLES
    )


def test_context_hash_is_stable_and_binds_to_results_and_model(monkeypatch):
    record = sample_record()
    explorer = [{"proposed_current_A (hypothetical)": 0.5}]

    first = make_context_hash(record, explorer)
    assert first == make_context_hash(sample_record(), explorer)
    assert len(first) == 64

    changed = sample_record()
    changed["results"]["slope"] += 1
    assert make_context_hash(changed, explorer) != first

    monkeypatch.setattr(ask_muse, "MODEL", "meta-models/muse-spark-open-1026")
    assert make_context_hash(sample_record(), explorer) != first


def test_analysis_record_is_complete_and_json_serializable():
    record = sample_record()

    assert record["application_version"] == "1.1.0"
    assert record["model"]["equation"] == "V = mI + b"
    assert record["row_counts"]["retained"] == 11
    assert record["input_sha256"] == "a" * 64
    assert record["ai_interpretation_generated"] is False
    assert record["warnings"]
    assert "python" in record["software_versions"]
    assert json.dumps(record, allow_nan=False)
