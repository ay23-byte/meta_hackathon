"""Educational templates never infer roles or compute physical parameters."""
from experiment_templates import TEMPLATES


def test_five_explicit_scientific_guides_have_assumptions():
    assert len(TEMPLATES) == 5
    for guidance in TEMPLATES.values():
        assert all(guidance.get(key) for key in ("x", "y", "model", "parameters", "assumptions"))
    assert "small-angle" in TEMPLATES["Simple pendulum"]["model"]
    assert "L0" in TEMPLATES["Linear thermal expansion"]["parameters"]
