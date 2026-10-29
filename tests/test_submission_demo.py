"""Offline integrated synthetic workflow; no real provider is contacted."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_comparison_theory_mock_and_pdf(monkeypatch):
    monkeypatch.setenv("LABLENS_DISABLE_DOTENV", "1")
    app = AppTest.from_file(str(ROOT / "general_app.py"), default_timeout=180).run()
    a = (ROOT / "data/demo/synthetic_ohmic_a.csv").read_bytes()
    b = (ROOT / "data/demo/synthetic_ohmic_b.csv").read_bytes()
    next(w for w in app.file_uploader if w.label == "Upload a delimited text file").set_value(
        ("synthetic_ohmic_a.csv", a, "text/csv")).run()
    next(w for w in app.text_input if w.label == "X unit (optional)").set_value("A")
    next(w for w in app.text_input if w.label == "Y unit (optional)").set_value("V")
    app.run()
    next(w for w in app.checkbox if w.label == "Enable proposed Ohmic model comparison").check().run()
    next(w for w in app.number_input if w.label == "Proposed resistance (ohm)").set_value(10.).run()
    next(w for w in app.checkbox if w.label.startswith("I confirm X is current, Y is voltage and this resistance")).check().run()
    assert any("Observed minus theoretical voltage" in t.value for t in app.text)
    next(w for w in app.button if w.label.startswith("Preview deterministic OFFLINE MOCK report")).click().run()
    assert any("OFFLINE MOCK" in x.value for x in app.markdown)
    next(w for w in app.file_uploader if w.label == "Second experiment CSV").set_value(
        ("synthetic_ohmic_b.csv", b, "text/csv")).run()
    next(w for w in app.text_input if w.label == "Second experiment X unit").set_value("A")
    next(w for w in app.text_input if w.label == "Second experiment Y unit").set_value("V")
    app.run()
    next(w for w in app.checkbox if w.label.startswith("I confirm the mapped quantities")).check().run()
    next(w for w in app.checkbox if w.label.startswith("Fit separate unweighted lines")).check().run()
    next(w for w in app.checkbox if w.label == "Include text-first PDF report in ZIP").check().run()
    assert not app.exception and not app.error
    assert any("Difference in paired Y means" in t.value for t in app.text)
    assert any("slope_difference_second_minus_first" in element.value for element in app.get("json"))
    assert any("OFFLINE MOCK" in x.value for x in app.markdown)
    # Report preview is intentionally limited; full report content is tested
    # by the export and PDF tests rather than assuming it fits in the preview.
    assert any("report.pdf" in c.value for c in app.caption)
    assert len(app.get("download_button")) == 3
