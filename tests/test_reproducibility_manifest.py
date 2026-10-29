"""Manifest must describe the real exported bytes without secrets."""
import hashlib
import json
from pathlib import Path

import pytest

from analyze_dataset import analyze_csv
from result_schema import export_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_cli_manifest_matches_artifacts_and_analysis(tmp_path, monkeypatch):
    secret = "unit-test-secret-for-manifest"
    monkeypatch.setenv("BASETEN_API_KEY", secret)
    result = analyze_csv(ROOT / "data/sample_voltage_current.csv", tmp_path, x="current_A", y="voltage_V")
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset"]["sha256"] == result["source"]["sha256"]
    assert manifest["configuration"]["x"] == result["roles"]["x"]
    assert manifest["provider"]["mode"] == "offline"
    assert manifest["evidence_fingerprint"] == result["evidence_ledger"]["analysis_fingerprint"]
    assert secret not in json.dumps(manifest)
    assert all(item["name"] != "manifest.json" for item in manifest["artifacts"])
    for item in manifest["artifacts"]:
        data = (tmp_path / item["name"]).read_bytes()
        assert len(data) == item["bytes"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]


def test_mock_and_live_modes_and_core_artifact_protection():
    for source, mode in (("offline_mock", "mock"), ("live_provider", "live"), ("unknown", "unknown")):
        files = export_bundle({"ai": {"source": source, "model": "test-model"}})
        assert json.loads(files["manifest.json"])["provider"]["mode"] == mode
    for name in ("results.json", "report.md", "manifest.json"):
        with pytest.raises(ValueError, match="cannot replace"):
            export_bundle({}, charts={name: b"spoofed"})
