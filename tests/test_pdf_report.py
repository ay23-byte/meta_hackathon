"""Actual PDF generation, parsing, export and fallback tests."""
import hashlib
import io
import json
from pathlib import Path

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from analyze_dataset import analyze_csv
from pdf_report import MAX_REPORT_CHARS, render_report_pdf
from result_schema import export_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_cli_pdf_opens_and_matches_source_result(tmp_path):
    result = analyze_csv(ROOT / "data/sample_voltage_current.csv", tmp_path,
                         x="current_A", y="voltage_V", include_pdf=True)
    path = tmp_path / "report.pdf"
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) >= 1
    assert "LabLens AI" in text and "4.99091" in text
    assert "figures packaged separately" in text
    assert result["fit"]["parameters"]["slope"] == pytest.approx(4.9909090909)
    assert (tmp_path / "plots/scatter.png").is_file()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    pdf = next(item for item in manifest["artifacts"] if item["name"] == "report.pdf")
    assert pdf["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_pdf_limits_do_not_truncate_and_can_fall_back_to_markdown():
    with pytest.raises(ValueError, match="too large"):
        render_report_pdf("x" * (MAX_REPORT_CHARS + 1))
    with pytest.raises(ValueError, match="nonempty"):
        render_report_pdf("")
    files = export_bundle({"notes": ["safe"]})
    assert "report.pdf" not in files and files["report.md"]
    files = export_bundle({"notes": ["safe"]}, include_pdf=True)
    reader = PdfReader(io.BytesIO(files["report.pdf"]))
    assert "safe" in "\n".join(page.extract_text() for page in reader.pages)


def test_pdf_ui_opt_in_and_pdf_error_keeps_other_downloads(monkeypatch):
    import pdf_report

    app = AppTest.from_file(str(ROOT / "general_app.py"), default_timeout=120).run()
    pdf = next(w for w in app.checkbox if w.label == "Include text-first PDF report in ZIP")
    assert not pdf.value
    pdf.check().run()
    assert not app.exception and not app.error
    assert any("report.pdf" in c.value for c in app.caption)
    def failure(_):
        raise ValueError("test PDF failure")
    monkeypatch.setattr(pdf_report, "render_report_pdf", failure)
    app.run()
    assert not app.exception and not app.error
    assert any("PDF unavailable; other exports are preserved" in w.value for w in app.warning)
    assert len(app.get("download_button")) == 3


def test_pdf_embeds_generated_png_and_preserves_separate_artifact(tmp_path):
    analyze_csv(ROOT / "data/sample_voltage_current.csv", tmp_path,
                x="current_A", y="voltage_V", include_pdf=True)
    reader = PdfReader(str(tmp_path / "report.pdf"))
    figure_pages = [page for page in reader.pages if "Generated figure" in (page.extract_text() or "")]
    assert figure_pages
    assert any(page.images for page in figure_pages)
    assert any("plots/scatter.png" in page.extract_text() for page in figure_pages)
    assert (tmp_path / "plots/scatter.png").is_file()


def test_pdf_refuses_invalid_or_oversized_figure_instead_of_silently_omitting():
    with pytest.raises(ValueError, match="figure"):
        render_report_pdf("report", figures={"plots/bad.png": b"not a png"})
    with pytest.raises(ValueError, match="figure limit"):
        render_report_pdf("report", figures={f"plots/{i}.png": b"x" for i in range(13)})
    # The ordinary non-PDF bundle remains available separately.
    files = export_bundle({}, charts={"plots/bad.png": b"not a png"})
    assert files["plots/bad.png"] == b"not a png" and "report.md" in files
