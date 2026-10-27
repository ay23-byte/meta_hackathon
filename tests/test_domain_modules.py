"""Domain layers are explicit, assumption-bearing and never inferred from names."""

import numpy as np
import pytest

from domain_modules import apply_domain, list_domain_modules
from fitting_core import fit_model


@pytest.fixture
def linear_fit():
    x = np.linspace(0, 1, 11)
    return fit_model("linear", x, 5 * x + 0.01)


def test_registry_has_default_generic_module():
    modules = {m["id"]: m for m in list_domain_modules()}
    assert "generic" in modules
    assert modules["generic"]["assumptions"]
    assert len(modules) >= 4


def test_generic_mode_never_names_a_physical_constant(linear_fit):
    result = apply_domain("generic", linear_fit, {"x": "Current (A)", "y": "Voltage (V)"})
    assert result["module"] == "generic"
    assert result["derived"] == []
    assert not any("ohm" in item.lower() for item in result["hypotheses"])
    assert any("no physical constant" in warning.lower() for warning in result["warnings"])


def test_column_names_do_not_trigger_ohmic_interpretation(linear_fit):
    result = apply_domain("generic", linear_fit, {
        "x": "current_A", "y": "voltage_V", "unit_x": "A", "unit_y": "V",
        "filename": "ohms_law_experiment.csv",
    })
    assert result["module"] == "generic"
    assert result["derived"] == []


def test_ohmic_requires_matching_units_before_naming_resistance(linear_fit):
    result = apply_domain("ohmic", linear_fit, {
        "x": "current_A", "y": "voltage_V", "unit_x": "", "unit_y": "",
    })
    assert result["derived"][0]["name"].startswith("proportionality")
    assert result["derived"][0]["unit"] != "ohm"
    assert any("Units were not a recognised" in warning for warning in result["warnings"])


def test_ohmic_with_current_voltage_units_reports_candidate_resistance(linear_fit):
    result = apply_domain("ohmic", linear_fit, {
        "x": "current_A", "y": "voltage_V", "unit_x": "A", "unit_y": "V",
    })
    derived = result["derived"][0]
    assert derived["unit"] == "ohm"
    assert derived["value"] == pytest.approx(5.0, abs=1e-8)
    assert "HYPOTHESIS" in result["hypotheses"][0]
    assert any("assumption chosen by the user" in warning for warning in result["warnings"])


def test_ohmic_with_scaled_units_cancels_prefixes(linear_fit):
    result = apply_domain("ohmic", linear_fit, {"unit_x": "mA", "unit_y": "mV"})
    assert result["derived"][0]["value"] == pytest.approx(5.0, abs=1e-8)


def test_nonlinear_fit_cannot_be_called_ohmic():
    x = np.linspace(1, 5, 20)
    fit = fit_model("exponential", x, 2 * np.exp(0.3 * x) + 1)
    result = apply_domain("ohmic", fit, {"unit_x": "A", "unit_y": "V"})
    assert result["derived"] == []
    assert any("only defined here for a linear fit" in warning for warning in result["warnings"])


def test_calibration_reports_sensitivity_and_inverse_formula(linear_fit):
    result = apply_domain("calibration", linear_fit, {
        "unit_x": "uM", "unit_y": "AU", "x": "conc", "y": "absorbance",
    })
    assert result["derived"][0]["value"] == pytest.approx(5.0, abs=1e-8)
    assert "uM" in result["derived"][0]["unit"]
    assert any("inverse-prediction" in item["name"] for item in result["derived"])


def test_growth_module_computes_doubling_time_from_rate():
    x = np.linspace(0, 5, 30)
    fit = fit_model("exponential", x, 100 * np.exp(0.4 * x))
    result = apply_domain("growth", fit, {"unit_time": "h"})
    derived = result["derived"][0]
    assert derived["name"] == "doubling time"
    assert derived["value"] == pytest.approx(np.log(2) / 0.4, rel=1e-4)
    assert derived["unit"] == "h"


def test_failed_fit_never_produces_domain_quantities():
    failed = fit_model("linear", [1, 1], [1, 2])
    result = apply_domain("ohmic", failed, {"unit_x": "A", "unit_y": "V"})
    assert result["fit_success"] is False
    assert result["derived"] == []
