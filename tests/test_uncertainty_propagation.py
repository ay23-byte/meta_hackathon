"""Conditional first-order propagation of explicitly supplied inputs."""
import json
import math
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from result_schema import export_bundle
from uncertainty_engine import propagate_independent


@pytest.mark.parametrize("operation,value,uncertainty,unit", [
    ("sum", 12, 0.5, "V"),
    ("difference", 8, 0.5, "V"),
    ("product", 20, math.hypot(2 * .3, 10 * .4), "(V)·(V)"),
    ("ratio", 5, math.hypot(.3 / 2, 10 * .4 / 4), "(V)/(V)"),
])
def test_known_first_order_values(operation, value, uncertainty, unit):
    result = propagate_independent(operation, 10, .3, "V", 2, .4, "V", confirmed=True)
    assert result["value"] == pytest.approx(value)
    assert result["standard_uncertainty"] == pytest.approx(uncertainty)
    assert result["unit"] == unit and result["status"] == "conditional_user_supplied"
    assert "covariance" in result["assumptions"]


@pytest.mark.parametrize("args", [
    ("sum", 1, .1, "V", 2, .2, "mV", True),
    ("sum", 1, .1, "", 2, .2, "V", True),
    ("ratio", 1, .1, "V", 0, .2, "A", True),
    ("sum", 1, -.1, "V", 2, .2, "V", True),
    ("sum", float("nan"), .1, "V", 2, .2, "V", True),
    ("sum", 1, .1, "V", 2, .2, "V", False),
    ("not-an-expression", 1, .1, "V", 2, .2, "V", True),
])
def test_invalid_or_unconfirmed_inputs_raise(args):
    operation, a, ua, unita, b, ub, unitb, confirmed = args
    with pytest.raises(ValueError):
        propagate_independent(operation, a, ua, unita, b, ub, unitb, confirmed=confirmed)


def test_zero_value_and_near_zero_denominator():
    out = propagate_independent("product", 0, .1, "m", 2, .4, "s", confirmed=True)
    assert out["value"] == 0 and out["standard_uncertainty"] == pytest.approx(.2)
    out = propagate_independent("ratio", 2, .1, "m", .1, .1, "s", confirmed=True)
    assert "unreliable" in out["warning"]


def test_json_and_markdown_export_and_safe_untrusted_unit():
    result = {"propagation": propagate_independent("product", 2, .1, "<img src=x>", 3, .2, "s", confirmed=True)}
    files = export_bundle(result)
    assert json.loads(files["results.json"])["propagation"] == result["propagation"]
    report = files["report.md"].decode()
    assert "user supplied" in report and "<img" not in report
    assert "not measured or inferred" in report


def test_ui_requires_confirmation_and_resets_when_values_change(monkeypatch):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    app = Path(__file__).resolve().parents[1] / "general_app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    next(w for w in at.checkbox if w.label == "Enable independent-input propagation").check().run()
    next(w for w in at.number_input if w.label == "Value a").set_value(10.0)
    next(w for w in at.number_input if w.label == "Standard uncertainty of a").set_value(.3)
    next(w for w in at.number_input if w.label == "Value b").set_value(2.0)
    next(w for w in at.number_input if w.label == "Standard uncertainty of b").set_value(.4)
    next(w for w in at.text_input if w.label.startswith("Unit of a")).set_value("V")
    next(w for w in at.text_input if w.label.startswith("Unit of b")).set_value("V")
    at.run()
    checkbox = next(w for w in at.checkbox if w.label.startswith("I supplied these values"))
    assert not checkbox.value
    checkbox.check().run()
    assert not at.exception and not at.error
    assert any("Conditional result: 12 ± 0.5 V" in item.value for item in at.text)
    assert any("User-supplied uncertainty propagation" in item.value for item in at.code)
    next(w for w in at.number_input if w.label == "Value b").set_value(3.0).run()
    assert not next(w for w in at.checkbox if w.label.startswith("I supplied these values")).value
    assert not any("Conditional result:" in item.value for item in at.text)
