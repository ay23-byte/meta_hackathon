"""User-supplied, unit-aware prediction checks remain descriptive."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from evidence_trace import build_evidence_ledger
from result_schema import export_bundle
from theory_engine import validate_ohmic_prediction


def test_unit_conversion_and_residuals():
    check = validate_ohmic_prediction([1, 2, 3, float('nan')], [2, 5, 6, 1], unit_x="mA", unit_y="V", resistance_ohm=2000, confirmed=True)
    assert check["pairs_used"] == 3 and check["pairs_excluded"] == 1
    assert check["mean_residual"] == pytest.approx(1/3)
    assert check["rmse"] == pytest.approx((1/3)**.5)
    assert "no uncertainty" in check["limitations"]


@pytest.mark.parametrize("overrides", [{"confirmed": False}, {"unit_x": "s"}, {"resistance_ohm": -1}, {"resistance_ohm": float('inf')}])
def test_invalid_assumptions(overrides):
    args = dict(unit_x="A", unit_y="V", resistance_ohm=1., confirmed=True)
    args.update(overrides)
    with pytest.raises(ValueError):
        validate_ohmic_prediction([1, 2], [1, 2], **args)


def test_export_and_ledger():
    check = validate_ohmic_prediction([1, 2], [1, 2], unit_x="A", unit_y="V", resistance_ohm=1., confirmed=True)
    result = {"theory_validation": check}
    result["evidence_ledger"] = build_evidence_ledger(result)
    files = export_bundle(result)
    stored = json.loads(files["results.json"])
    assert stored["theory_validation"] == check
    assert any(item["result_path"] == "theory_validation" for item in stored["evidence_ledger"]["items"])
    assert "User-proposed Ohmic theory comparison" in files["report.md"].decode()


def test_ui_confirmation_resets_with_theory_change(monkeypatch):
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "general_app.py"), default_timeout=120).run()
    next(w for w in app.checkbox if w.label == "Enable proposed Ohmic model comparison").check().run()
    confirm = next(w for w in app.checkbox if w.label.startswith("I confirm X is current, Y is voltage and this resistance"))
    assert not confirm.value
    confirm.check().run()
    assert not app.exception
    next(w for w in app.number_input if w.label == "Proposed resistance (ohm)").set_value(5.).run()
    assert not next(w for w in app.checkbox if w.label.startswith("I confirm X is current, Y is voltage and this resistance")).value
