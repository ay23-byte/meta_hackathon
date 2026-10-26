import json
from io import StringIO

import numpy as np
import pandas as pd
import pytest

from analysis_core import (
    analyze_linear,
    detect_candidate_columns,
    prepare_analysis_data,
    propose_measurements,
    serialize_analysis_exports,
)
from ask_muse import (
    MAX_CLAIMS,
    MAX_SECTION_WORDS,
    REQUIRED_TITLES,
    build_prompt,
    describe_provider_status,
    generate_interpretation,
    validate_report,
)


def test_ambiguous_alias_requires_manual_choice():
    assert detect_candidate_columns(["current_A", "Current (A)"], "current") is None


def test_invalid_rows_and_source_correspondence():
    data = pd.DataFrame({"I (A)": [0, "bad", 2, 3], "V (V)": [1, 2, np.inf, 7]})
    prepared = prepare_analysis_data(data, "I (A)", "V (V)")
    assert prepared["original_rows"] == 4
    assert prepared["valid_rows"] == 2
    assert prepared["dropped_rows"] == 2
    assert prepared["data"]["source_row"].tolist() == [1, 4]


def test_proposal_is_hypothetical_and_marks_extrapolation():
    result = analyze_linear([0, 1, 2], [1, 3, 5])
    table = propose_measurements([1, 3], result, [0, 1, 2])
    assert table["predicted_voltage_V (model prediction)"].tolist() == pytest.approx([3, 7])
    assert table["within_observed_range"].tolist() == [True, False]
    assert "hypothetical" in table.columns[0]


def test_download_exports_are_strict_json_and_aligned_csv():
    result = analyze_linear([0, 1, 2], [1, 3, 4])
    clean = pd.DataFrame({"current_A": [0, 1, 2], "voltage_V": [1, 3, 4],
                          "fitted_voltage": result["fitted"], "residual_voltage": result["residuals"]})
    exports = serialize_analysis_exports({"results": {"rmse": result["rmse"], "r_squared": result["r_squared"]}}, clean, "# report")
    decoded = json.loads(exports["json"])
    exported = pd.read_csv(StringIO(exports["csv"]))
    assert decoded["results"]["rmse"] == pytest.approx(result["rmse"])
    assert exported["residual_voltage"].to_numpy() == pytest.approx(
        exported["voltage_V"].to_numpy() - exported["fitted_voltage"].to_numpy()
    )
    assert exports["markdown"] == "# report"


def test_muse_report_structure_validation_and_fallback():
    good = json.dumps({"sections": [{"title": title.title(), "content": "Limited evidence."} for title in sorted(REQUIRED_TITLES)], "claims": [{
        "claim": "Fit is linear", "evidence": "Computed slope", "evidence_type": "computed_result",
        "confidence_or_uncertainty": "Not calibrated", "limitation": "Small range", "proposed_verification": "Collect more points",
    }]})
    assert len(validate_report(good)["sections"]) == len(REQUIRED_TITLES)
    assert validate_report("not json") is None
    assert validate_report('{"sections":[{"title":"x","content":"y"}],"claims":[{"claim":"bad"}]}') is None


def test_muse_prompt_limits_report_size_without_omitting_sections():
    prompt = build_prompt({"results": {"n": 4, "rmse": 0.1}})
    assert f"at most {MAX_SECTION_WORDS} words" in prompt
    assert f"at most {MAX_CLAIMS} claims" in prompt
    for title in REQUIRED_TITLES:
        assert title in prompt


def test_generate_interpretation_requires_api_key_and_is_secret_free(
    monkeypatch,
):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        generate_interpretation({"results": {"n": 2}})

    message = str(exc_info.value)
    assert "BASETEN_API_KEY" in message
    # Error messages must never leak the secret itself.
    assert "your_baseten_api_key_here" not in message


def test_app_ai_report_validation_enforces_required_schema():
    from app import validate_ai_report

    good = {
        "model": "meta-models/muse-spark-open",
        "structured": {
            "sections": [
                {"title": title, "content": "Short content here."}
                for title in sorted(REQUIRED_TITLES)
            ],
            "claims": [
                {
                    "claim": "Fit is linear",
                    "evidence": "Computed slope",
                    "evidence_type": "computed_result",
                    "confidence_or_uncertainty": "Not calibrated",
                    "limitation": "Small range",
                    "proposed_verification": "Collect more points",
                }
            ],
        },
    }
    assert validate_ai_report(good) is True

    # Missing sections are rejected.
    incomplete = json.loads(json.dumps(good))
    incomplete["structured"]["sections"] = incomplete["structured"][
        "sections"
    ][:2]
    assert validate_ai_report(incomplete) is False

    # Duplicate sections are rejected.
    duplicate = json.loads(json.dumps(good))
    duplicate["structured"]["sections"] = [
        {"title": REQUIRED_TITLES[0], "content": "First."},
        {"title": REQUIRED_TITLES[0], "content": "Second."},
    ]
    assert validate_ai_report(duplicate) is False

    # Claims missing required evidence fields are rejected.
    bad_claim = json.loads(json.dumps(good))
    bad_claim["structured"]["claims"] = [{"claim": "only a claim"}]
    assert validate_ai_report(bad_claim) is False


def test_export_row_counts_and_metrics_match_analysis():
    result = analyze_linear([0, 1, 2], [1, 3, 4])
    clean = pd.DataFrame(
        {
            "current_A": [0, 1, 2],
            "voltage_V": [1, 3, 4],
            "fitted_voltage": result["fitted"],
            "residual_voltage": result["residuals"],
        }
    )
    record = {
        "results": {
            "slope": result["slope"],
            "intercept": result["intercept"],
            "r_squared": result["r_squared"],
            "rmse": result["rmse"],
            "n": result["n"],
        }
    }
    exports = serialize_analysis_exports(record, clean, "# report")

    decoded = json.loads(exports["json"])
    assert decoded["results"]["slope"] == pytest.approx(result["slope"])
    assert decoded["results"]["n"] == result["n"]

    exported = pd.read_csv(StringIO(exports["csv"]))
    assert len(exported) == result["n"]
    assert exported["residual_voltage"].to_numpy() == pytest.approx(
        exported["voltage_V"].to_numpy()
        - exported["fitted_voltage"].to_numpy()
    )


@pytest.mark.parametrize("status,needle", [(401, "BASETEN_API_KEY"), (403, "permissions"), (404, "model"), (429, "quota")])
def test_provider_status_errors_are_actionable_and_secret_free(status, needle):
    message = describe_provider_status(status)
    assert f"HTTP {status}" in message
    assert needle.casefold() in message.casefold()
