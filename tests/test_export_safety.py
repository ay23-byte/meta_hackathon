"""Export validity, mutual consistency, secret safety and archive path safety."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import analyze_dataset
from result_schema import export_bundle, safe_archive_name

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_voltage_current.csv"
SECRET = "sk-EXPORT-SECRET-SHOULD-NOT-APPEAR-000"


@pytest.mark.parametrize("name", [
    "../evil.csv", "/abs.csv", "C:/evil.csv", "plots\\evil.csv", "a/../b.csv",
    "a//b.csv", "~/secret.csv", "a/./b.csv", "", " bad.csv", "bad\n.csv",
])
def test_unsafe_archive_names_are_rejected(name):
    with pytest.raises(ValueError, match=r"Export file name|unsafe path|relative"):
        safe_archive_name(name)


@pytest.mark.parametrize("name", [
    "results.json", "plots/scatter.png", "agent/agent_audit.json",
])
def test_normal_relative_archive_names_are_accepted(name):
    assert safe_archive_name(name) == name


def test_export_bundle_rejects_unsafe_chart_name(tmp_path):
    result = analyze_dataset.analyze_csv(SAMPLE, tmp_path)
    with pytest.raises(ValueError, match="unsafe path"):
        export_bundle(result, charts={"../evil.png": b"not safe"})


def test_cli_rejects_unsafe_export_names_before_writing_anything(tmp_path, monkeypatch):
    monkeypatch.setattr(
        analyze_dataset, "export_bundle",
        lambda *args, **kwargs: {"../evil.csv": b"should not escape"},
    )
    with pytest.raises(ValueError, match="unsafe path"):
        analyze_dataset.analyze_csv(SAMPLE, tmp_path)
    assert not (tmp_path.parent / "evil.csv").exists()


def test_general_app_zip_writer_validates_names():
    source = (ROOT / "general_app.py").read_text(encoding="utf-8")
    assert "archive.writestr(safe_archive_name(name), payload)" in source


def _build_zip(files: dict[str, bytes]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(safe_archive_name(name), payload)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def test_cli_exports_are_valid_consistent_and_secret_free(monkeypatch, tmp_path):
    monkeypatch.setenv("BASETEN_API_KEY", SECRET)
    result = analyze_dataset.analyze_csv(SAMPLE, tmp_path, generate_ai=False)

    json_bytes = (tmp_path / "results.json").read_bytes()
    data = json.loads(json_bytes)
    assert data["schema_version"] == "2.0"
    assert b"NaN" not in json_bytes and b"Infinity" not in json_bytes
    assert SECRET.encode() not in json_bytes
    assert data.get("ai") is None

    slope = result["fit"]["parameters"]["slope"]
    r2 = result["fit"]["metrics"]["r2"]
    params_csv = (tmp_path / "fit_parameters.csv").read_text(encoding="utf-8-sig")
    metrics_csv = (tmp_path / "fit_metrics.csv").read_text(encoding="utf-8-sig")
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    cleaned = (tmp_path / "cleaned_data.csv").read_bytes()

    params_df = pd.read_csv(io.StringIO(params_csv))
    metrics_df = pd.read_csv(io.StringIO(metrics_csv))
    csv_slope = params_df.loc[params_df["parameter"] == "slope", "value"].iloc[0]
    csv_r2 = metrics_df.loc[metrics_df["metric"] == "r2", "value"].iloc[0]
    assert csv_slope == pytest.approx(slope, rel=1e-9)
    assert csv_r2 == pytest.approx(r2, rel=1e-9)
    assert "## 5. Fit" in report and "4.99091" in report
    assert "Provider model:" not in report
    assert "Not requested, or the provider was unavailable" in report
    assert "OFFLINE MOCK" not in report
    assert cleaned.startswith(b"\xef\xbb\xbf")
    assert len(cleaned.decode("utf-8-sig").strip().splitlines()) == result["source"]["rows"] + 1

    files = export_bundle(
        result,
        cleaned_frame=pd.DataFrame({"x": [1.0, 2.0], "y": [2.0, 4.0]}),
        descriptive_table=pd.DataFrame({"column": ["x"], "mean": [1.5]}),
        charts={"plots/demo.html": b"<html>offline-ok</html>"},
    )
    for required in ("results.json", "cleaned_data.csv", "statistics.csv",
                     "fit_parameters.csv", "fit_metrics.csv", "report.md",
                     "plots/demo.html"):
        assert files.get(required)

    with _build_zip(files) as archive:
        names = archive.namelist()
        assert all(not name.startswith("/") and ".." not in name.split("/")
                   and "\\" not in name for name in names)
        assert not any(name.endswith(".env") or "secret" in name.casefold()
                       or "credential" in name.casefold() for name in names)
        assert all(archive.read(name) for name in names)
        assert all(SECRET.encode() not in archive.read(name) for name in names)


def test_csv_export_neutralizes_formula_like_cells():
    frame = pd.DataFrame({"value": ["=1+1", "+SUM(A1)", "@cmd", "-1", "2"]})
    files = export_bundle(
        {"source": {}, "roles": {}, "cleaning": {}, "statistics": {},
         "correlation": {}, "outliers": {}, "fit": None,
         "model_comparison": [], "model_suggestions": [], "domain": {},
         "visualizations": [], "notes": [], "warnings": [], "ai": None},
        cleaned_frame=frame,
    )
    lines = files["cleaned_data.csv"].decode("utf-8-sig").strip().splitlines()
    for line in lines[1:]:
        assert not line.startswith(("=", "+", "@", "-"))


def test_markdown_report_separates_live_ai_and_offline_mock(tmp_path):
    result = analyze_dataset.analyze_csv(SAMPLE, tmp_path)
    sections = [
        {"title": title, "content": f"Computed note {index}."}
        for index, title in enumerate(
            ("Executive Summary", "Observed Pattern", "Model and Assumptions",
             "Quantitative Results", "Scientific Interpretation",
             "Uncertainty and Limitations", "Proposed Verification", "Conclusion")
        )
    ]
    result["ai"] = {"model": "meta-models/muse-spark-open", "source": "live_provider",
                    "is_mock": False, "structured": {"sections": sections, "claims": []}}
    live_report = export_bundle(result)["report.md"].decode("utf-8")
    assert "AI-generated interpretation (unverified hypotheses)" in live_report
    assert "OFFLINE MOCK" not in live_report

    result["ai"] = {
        "model": "offline-deterministic-mock", "source": "offline_mock",
        "is_mock": True, "disclaimer": "OFFLINE MOCK REPORT - NOT AI",
        "structured": {"sections": sections, "claims": []},
    }
    mock_report = export_bundle(result)["report.md"].decode("utf-8")
    assert "OFFLINE MOCK report (deterministic template, NOT AI)" in mock_report
    assert "NOT AI" in mock_report
    assert "AI-generated interpretation" not in mock_report


def test_cli_preflights_all_targets_before_any_write(tmp_path, monkeypatch):
    monkeypatch.setattr(analyze_dataset, "export_bundle",
                        lambda *args, **kwargs: {"first.txt": b"first", "../escape.txt": b"bad"})
    with pytest.raises(ValueError):
        analyze_dataset.analyze_csv(SAMPLE, tmp_path)
    assert not (tmp_path / "first.txt").exists()


def test_cli_never_overwrites_its_input_dataset(tmp_path):
    source = tmp_path / "cleaned_data.csv"
    original = SAMPLE.read_bytes()
    source.write_bytes(original)
    with pytest.raises(ValueError, match="overwrite the input"):
        analyze_dataset.analyze_csv(source, tmp_path)
    assert source.read_bytes() == original
    assert not (tmp_path / "results.json").exists()


def test_cli_refuses_symlink_export_targets(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    try:
        (output / "plots").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")
    with pytest.raises(ValueError, match="symbolic link"):
        analyze_dataset.analyze_csv(SAMPLE, output)
    assert not list(outside.iterdir())
    assert not (output / "results.json").exists()


def test_cli_refuses_hard_link_to_input(tmp_path):
    import os

    source = tmp_path / "input.csv"
    source.write_bytes(SAMPLE.read_bytes())
    original = source.read_bytes()
    out = tmp_path / "out"
    out.mkdir()
    try:
        os.link(source, out / "results.json")
    except (OSError, NotImplementedError):
        pytest.skip("Hard links are unavailable in this environment")
    with pytest.raises(ValueError, match="overwrite the input"):
        analyze_dataset.analyze_csv(source, out)
    assert source.read_bytes() == original
