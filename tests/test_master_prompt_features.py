"""Master-prompt regression tests: scientific reports, evidence, mock, agent Q&A.

All provider calls are faked locally. No test in this file requires a real
BASETEN_API_KEY or network access.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_planner as planner
import ask_muse
from agent_core import AnalysisOrchestrator, OrchestratorConfig
from agent_tools import registry_manifest
from data_io import read_csv_robust
from result_schema import ai_context, evidence_index, markdown_report

SECRET = "sk-unit-test-DO-NOT-LEAK-13579"
ROOT = Path(__file__).resolve().parents[1]
CASE_A = ROOT / "data" / "agent_examples" / "case_a_linear.csv"


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"provider returned {status_code}")
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        self.client.calls.append(kwargs)
        outcome = self.client.outcomes[min(len(self.client.calls) - 1,
                                           len(self.client.outcomes) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes, init_kwargs):
        self.outcomes = list(outcomes)
        self.init_kwargs = init_kwargs
        self.calls = []
        self.chat = SimpleNamespace(completions=FakeCompletions(self))


def response(content, *, finish_reason="stop"):
    message = SimpleNamespace(content=content, model_extra={})
    return SimpleNamespace(
        model="meta-models/muse-spark-open",
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
    )


def report_for(titles, *, claims=None):
    return {
        "sections": [{"title": title, "content": f"Computed note {i}."}
                     for i, title in enumerate(titles)],
        "claims": claims if claims is not None else [],
    }


@pytest.fixture
def fake_provider(monkeypatch):
    created = []

    def install(outcomes, *, key=True):
        if key:
            monkeypatch.setenv("BASETEN_API_KEY", SECRET)
        else:
            monkeypatch.delenv("BASETEN_API_KEY", raising=False)

        def factory(**kwargs):
            client = FakeClient(outcomes, kwargs)
            created.append(client)
            return client

        monkeypatch.setattr(ask_muse, "OpenAI", factory)
        return created

    return install


# ---------------------------------------------------------------------------
# Strict report profiles and evidence-linked claims
# ---------------------------------------------------------------------------

def test_scientific_profile_is_independent_of_legacy_default():
    assert ask_muse.DEFAULT_REPORT_PROFILE == "legacy"
    assert ask_muse.resolve_section_titles() == ask_muse.REQUIRED_TITLES
    assert ask_muse.resolve_section_titles(profile="scientific") == \
        ask_muse.SCIENTIFIC_REPORT_TITLES
    assert "Research Question" in ask_muse.section_registry("scientific")
    assert "Research Question" not in ask_muse.section_registry("legacy")
    with pytest.raises(ValueError, match="Unknown report profile"):
        ask_muse.resolve_section_titles(profile="unknown")
    with pytest.raises(ValueError, match="Unexpected report section"):
        ask_muse.resolve_section_titles(["Executive Summary"], profile="scientific")

    prompt = ask_muse.build_prompt({"results": {"n": 3}}, profile="scientific")
    assert "Research Question" in prompt
    assert "8 sections exactly once" in prompt


def test_scientific_report_validates_only_scientific_sections():
    scientific = report_for(ask_muse.SCIENTIFIC_REPORT_TITLES)
    assert ask_muse.validate_report(scientific, profile="scientific") is not None
    assert ask_muse.validate_report(scientific) is None
    assert ask_muse.validate_report(report_for(ask_muse.REQUIRED_TITLES),
                                    profile="scientific") is None


def test_prompt_requires_evidence_ids_when_result_ids_exist():
    context = {"results": {"r2": 0.99}, "result_ids": ["fit.linear", "dataset.source"]}
    prompt = ask_muse.build_prompt(context)
    assert "evidence_ids" in prompt
    assert "chosen only from the `result_ids`" in prompt
    assert "evidence_ids" not in ask_muse.build_prompt({"results": {"r2": 0.99}})


def test_validate_report_enforces_computed_evidence_ids():
    titles = ask_muse.SCIENTIFIC_REPORT_TITLES
    claim = {
        "claim": "The computed fit is strong.",
        "evidence": "R2 from the computed fit block.",
        "evidence_type": "computed_result",
        "confidence_or_uncertainty": "No calibration uncertainty was supplied.",
        "limitation": "Only this dataset was measured.",
        "proposed_verification": "Repeat with independent measurements.",
        "evidence_ids": ["fit.linear"],
    }
    allowed = ["fit.linear", "dataset.source"]
    good = report_for(titles, claims=[claim])
    clean = ask_muse.validate_report(good, profile="scientific",
                                     allowed_evidence_ids=allowed)
    assert clean is not None
    assert clean["claims"][0]["evidence_ids"] == ["fit.linear"]

    for bad_ids in (None, [], ["invented-id"], ["fit.linear", "fit.linear"],
                    ["fit.linear"] * 5, "fit.linear", ["x" * 100]):
        broken = json.loads(json.dumps(good))
        broken["claims"][0]["evidence_ids"] = bad_ids
        assert ask_muse.validate_report(
            broken, profile="scientific", allowed_evidence_ids=allowed
        ) is None
    # Without an allowlist the untrusted field is dropped rather than exported.
    dropped = ask_muse.validate_report(good, profile="scientific")
    assert dropped is not None and "evidence_ids" not in dropped["claims"][0]


def test_live_wrapper_is_explicitly_marked_live(fake_provider):
    created = fake_provider([response(json.dumps(report_for(ask_muse.REQUIRED_TITLES)))])
    wrapper = ask_muse.generate_interpretation({"results": {"n": 3}})
    assert wrapper["source"] == "live_provider" and wrapper["is_mock"] is False
    assert wrapper["profile"] == "legacy"
    assert SECRET not in json.dumps(wrapper)
    assert len(created[-1].calls) == 1


def test_scientific_live_report_round_trip_requires_evidence_ids(fake_provider):
    context = {"results": {"r2": 0.9998}, "result_ids": ["fit.linear"]}
    claim = {
        "claim": "The fit reports R2 0.9998.",
        "evidence": "Computed fit metrics in the supplied context.",
        "evidence_type": "computed_result",
        "confidence_or_uncertainty": "No measurement uncertainty was supplied.",
        "limitation": "This is one synthetic dataset.",
        "proposed_verification": "Collect validation data.",
        "evidence_ids": ["fit.linear"],
    }
    fake_provider([response(json.dumps(report_for(
        ask_muse.SCIENTIFIC_REPORT_TITLES, claims=[claim])))])
    wrapper = ask_muse.generate_interpretation(context, profile="scientific")
    assert [s["title"] for s in wrapper["structured"]["sections"]] == \
        list(ask_muse.SCIENTIFIC_REPORT_TITLES)
    assert wrapper["structured"]["claims"][0]["evidence_ids"] == ["fit.linear"]


def test_transient_retries_are_bounded_but_non_transient_errors_are_not_retried(
        fake_provider, monkeypatch):
    monkeypatch.setattr(ask_muse, "TRANSIENT_BACKOFF_SECONDS", 0)
    created = fake_provider([HttpError(503),
                             response(json.dumps(report_for(ask_muse.REQUIRED_TITLES)))])
    wrapper = ask_muse.generate_interpretation({"results": {"n": 3}})
    assert wrapper["source"] == "live_provider"
    assert len(created[-1].calls) == 2

    created = fake_provider([HttpError(503)])
    with pytest.raises(RuntimeError, match="HTTP 503"):
        ask_muse.generate_interpretation({"results": {"n": 3}})
    assert len(created[-1].calls) == ask_muse.MAX_TRANSIENT_RETRIES + 1 == 3

    created = fake_provider([HttpError(401)])
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY"):
        ask_muse.generate_interpretation({"results": {"n": 3}})
    assert len(created[-1].calls) == 1


# ---------------------------------------------------------------------------
# Honest provider status and the explicitly labelled offline mock
# ---------------------------------------------------------------------------

def test_provider_status_never_claims_live_verification(fake_provider):
    fake_provider([], key=False)
    offline = ask_muse.provider_status()
    assert offline["api_key_configured"] is False
    assert offline["mode"] == "offline"
    assert offline["live_verified"] is False and offline["live_call_attempted"] is False
    assert offline["offline_mock_available"] is True

    fake_provider([], key=True)
    configured = ask_muse.provider_status()
    assert configured["api_key_configured"] is True
    assert configured["mode"] == "live_unverified"
    assert configured["live_verified"] is False
    assert SECRET not in json.dumps(configured)


def test_offline_mock_is_labelled_grounded_and_schema_valid():
    context = {
        "source": {"rows": 11, "columns": ["x", "y"]},
        "cleaning": {"rows_in": 11, "rows_out": 11},
        "fit": {"success": True, "model": "linear", "label": "y = a x + b",
                "parameters": {"slope": 4.99, "intercept": 0.005},
                "metrics": {"r2": 0.9998, "rmse": 0.022},
                "n_observations": 11},
        "correlation": {"coefficient": 0.9999},
        "research_question": "What is the slope?",
        "result_ids": ["fit.linear", "dataset.source"],
        "evidence_index": {"fit.linear": {"r2": 0.9998},
                           "dataset.source": {"rows": 11}},
    }
    mock = ask_muse.generate_mock_report(context, profile="scientific")
    assert mock["source"] == "offline_mock" and mock["is_mock"] is True
    assert "NOT a Muse Spark response" in mock["disclaimer"]
    assert "NOT AI" in mock["disclaimer"]
    assert [s["title"] for s in mock["structured"]["sections"]] == \
        list(ask_muse.SCIENTIFIC_REPORT_TITLES)
    text = json.dumps(mock["structured"])
    assert "4.99" in text and "0.9998" in text and "12345" not in text
    assert mock["structured"]["claims"][0]["evidence_ids"] == ["fit.linear"]
    assert ask_muse.validate_report(
        mock["structured"], profile="scientific",
        allowed_evidence_ids=context["result_ids"],
    ) is not None
    report = markdown_report({"ai": mock, "source": context["source"]})
    assert "OFFLINE MOCK report" in report and "NOT AI" in report
    assert "NOT a Muse Spark response" in report


def test_evidence_index_ids_are_valid_and_context_is_bounded():
    result = {
        "source": {"name": "a.csv", "rows": 3, "columns": ["x", "y"], "sha256": "a" * 64},
        "cleaning": {"rows_in": 3, "rows_out": 3},
        "correlation": {"method": "pearson", "coefficient": 1.0},
        "fit": {"success": True, "model": "linear", "parameters": {"slope": 2.0},
                "metrics": {"r2": 1.0, "rmse": 0.0}, "n_observations": 3},
        "statistics": {"x": {"n_valid": 3, "mean": 1.0}},
        "outliers": {"n_valid": 3, "n_low": 0, "n_high": 0},
    }
    index = evidence_index(result)
    assert index and all(ask_muse._EVIDENCE_ID_RE.fullmatch(key) for key in index)
    context = ai_context(result, research_question="What is the trend?",
                         max_chars=4000)
    assert context["research_question"] == "What is the trend?"
    assert context["result_ids"] == list(context["evidence_index"])
    assert len(json.dumps(context)) <= 4000


# ---------------------------------------------------------------------------
# Bounded agent: research question, clarification, plan prompt
# ---------------------------------------------------------------------------

def test_agent_ambiguous_question_stops_before_any_tool_and_offers_options():
    load = read_csv_robust(CASE_A, source_name=CASE_A.name)
    data = AnalysisOrchestrator(OrchestratorConfig(
        use_ai=False, research_question="Is it good?",
    )).run(load).to_dict()
    assert data["final"]["state"] == "NEEDS_CLARIFICATION"
    assert data["question_source"] == "user"
    assert data["research_question"] == "Is it good?"
    assert data["final"]["clarification"]["needed"] is True
    assert len(data["final"]["clarification"]["options"]) == 3
    assert all(event["tool"] is None for event in data["events"])
    assert any("clarification" in event["decision"].lower()
               for event in data["events"])


def test_agent_actionable_question_is_logged_and_analysis_proceeds():
    load = read_csv_robust(CASE_A, source_name=CASE_A.name)
    question = "How does signal_mV vary with t_s?"
    data = AnalysisOrchestrator(OrchestratorConfig(
        use_ai=False, research_question=question,
    )).run(load).to_dict()
    assert data["final"]["state"] == "DONE"
    assert data["research_question"] == question
    assert data["question_source"] == "user"
    assert data["events"][0]["phase"] == "question"
    assert any(event["tool"] == "fit_curve" for event in data["events"])


def test_plan_prompt_and_ai_digest_include_the_research_question():
    question = "Compare the trend of y against x."
    prompt = planner.build_plan_prompt(
        {"numeric_columns": ["x", "y"]}, registry_manifest(), question
    )
    assert question in prompt
    assert "Tailor the steps to the supplied research question" in prompt

    from agent_audit import AgentRun

    run = AgentRun(dataset={"name": "a.csv"}, research_question=question,
                   question_source="user")
    assert run.digest_for_ai()["research_question"] == question


def test_demo_d_and_e_are_reproducible_offline(tmp_path, capsys):
    import run_agent_demo

    assert run_agent_demo.main(["--case", "d", "--strict",
                                "--output-dir", str(tmp_path)]) == 0
    d = json.loads((tmp_path / "d" / "agent_audit.json").read_text(encoding="utf-8"))
    assert d["final"]["state"] == "NEEDS_CLARIFICATION"
    assert len(d["final"]["clarification"]["options"]) == 3

    assert run_agent_demo.main(["--case", "e", "--strict",
                                "--output-dir", str(tmp_path)]) == 0
    e = json.loads((tmp_path / "e" / "agent_audit.json").read_text(encoding="utf-8"))
    assert e["final"]["state"] == "DONE"
    assert e["plan_source"] == "deterministic_fallback"
    assert any(event["phase"] == "plan" and event["status"] == "unavailable"
               for event in e["events"])
    status = json.loads((tmp_path / "e" / "provider_status.json").read_text(encoding="utf-8"))
    assert status["simulated_outage"] is True
    assert status["live_verified"] is False
    mock_text = (tmp_path / "e" / "offline_mock_report.md").read_text(encoding="utf-8")
    assert "NOT a Muse Spark response" in mock_text
    assert "NOT AI" in mock_text
    assert "3.25541" in mock_text  # computed slope from the synthetic case
