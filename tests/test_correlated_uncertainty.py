"""Analytical and seeded simulation tests for user-supplied uncertainty."""
import json
import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from evidence_trace import build_evidence_ledger
from result_schema import export_bundle
from uncertainty_engine import monte_carlo_correlated, propagate_correlated


def calculate(op, rho):
    return propagate_correlated(op, 10, .3, "V", 2, .4, "V", correlation=rho, confirmed=True)


@pytest.mark.parametrize("op,ca,cb", [("sum", .3, .4), ("difference", .3, -.4),
                                     ("product", .6, 4.), ("ratio", .15, -1.)])
@pytest.mark.parametrize("rho", [-1., -.5, 0., .7, 1.])
def test_correlated_first_order_matches_analytical_formula(op, ca, cb, rho):
    result = calculate(op, rho)
    assert result["standard_uncertainty"] == pytest.approx(math.sqrt(max(0, ca**2 + cb**2 + 2*rho*ca*cb)))
    assert result["inputs"]["correlation"] == rho
    assert "not inferred" in result["assumptions"]


def test_seeded_normal_sum_quantiles_agree_with_analytical_reference():
    params = dict(correlation=.5, confirmed=True, seed=123, samples=50_000)
    a = monte_carlo_correlated("sum", 10, .3, "V", 2, .4, "V", **params)
    b = monte_carlo_correlated("sum", 10, .3, "V", 2, .4, "V", **params)
    assert a == b
    sigma = math.sqrt(.3**2 + .4**2 + 2 * .5 * .3 * .4)
    assert a["median"] == pytest.approx(12, abs=.015)
    assert a["lower_2_5_percent"] == pytest.approx(12 - 1.95996 * sigma, abs=.03)
    assert a["upper_97_5_percent"] == pytest.approx(12 + 1.95996 * sigma, abs=.03)
    assert "not a confidence" in a["limitations"]


@pytest.mark.parametrize("rho", [float('nan'), -1.1, 1.1, True])
def test_invalid_correlation_is_rejected(rho):
    with pytest.raises(ValueError):
        calculate("sum", rho)


def test_invalid_simulation_parameters_and_zero_denominator_are_rejected():
    with pytest.raises(ValueError, match="zero correlation"):
        propagate_correlated("sum", 1, 0, "V", 2, .1, "V", correlation=.5, confirmed=True)
    with pytest.raises(ValueError, match="five standard"):
        monte_carlo_correlated("ratio", 2, .1, "V", .1, .1, "A", correlation=0, confirmed=True, seed=2)
    with pytest.raises(ValueError, match="Seed"):
        monte_carlo_correlated("sum", 1, .1, "V", 2, .1, "V", correlation=0, confirmed=True, seed=-1)
    with pytest.raises(ValueError, match="sample count"):
        monte_carlo_correlated("sum", 1, .1, "V", 2, .1, "V", correlation=0, confirmed=True, seed=1, samples=999)
    with pytest.raises(ValueError):
        propagate_correlated("sum", 1, .1, "V", 2, .1, "V", correlation=0, confirmed=False)


def test_export_links_simulation_and_records_seed():
    cor = calculate("sum", .5)
    mc = monte_carlo_correlated("sum", 10, .3, "V", 2, .4, "V", correlation=.5, confirmed=True, seed=17)
    result = {"correlated_propagation": cor, "monte_carlo_propagation": mc}
    result["evidence_ledger"] = build_evidence_ledger(result)
    files = export_bundle(result)
    stored = json.loads(files["results.json"])
    assert stored["monte_carlo_propagation"] == mc
    assert json.loads(files["manifest.json"])["simulation"]["seed"] == 17
    report = files["report.md"].decode()
    assert "Correlated user-supplied" in report and "Monte Carlo propagation" in report
    assert any(item["result_path"] == "monte_carlo_propagation" for item in stored["evidence_ledger"]["items"])


def test_ui_requires_confirmation_and_invalidates_after_change(monkeypatch):
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=120).run()
    next(w for w in app.checkbox if w.label == "Enable correlated-input calculator").check().run()
    next(w for w in app.number_input if w.label == "Correlated value a").set_value(10.)
    next(w for w in app.number_input if w.label == "Correlated uncertainty a").set_value(.3)
    next(w for w in app.number_input if w.label == "Correlated value b").set_value(2.)
    next(w for w in app.number_input if w.label == "Correlated uncertainty b").set_value(.4)
    next(w for w in app.text_input if w.label == "Correlated unit a (1 if dimensionless)").set_value("V")
    next(w for w in app.text_input if w.label == "Correlated unit b (1 if dimensionless)").set_value("V")
    next(w for w in app.checkbox if w.label.startswith("Also simulate")).check().run()
    confirm = next(w for w in app.checkbox if w.label.startswith("I confirm the entered values"))
    assert not confirm.value
    confirm.check().run()
    assert not app.exception and not app.error
    assert any("Simulated median" in t.value for t in app.text)
    assert any("Monte Carlo propagation" in c.value for c in app.code)
    next(w for w in app.number_input if w.label == "Monte Carlo seed").set_value(17).run()
    assert not next(w for w in app.checkbox if w.label.startswith("I confirm the entered values")).value
