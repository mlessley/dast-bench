import json

from typer.testing import CliRunner

from core import storage
from core.cli import app
from core.models import Benchmark, BenchmarkVulnerability

runner = CliRunner()


def _setup_vendor_and_benchmark(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["candidate", "add", "--id", "v1", "--name", "Vendor One", "--source", "discovered"])
    benchmarks_path = tmp_path / "data" / "benchmarks.yaml"
    storage.save_benchmarks(
        [
            Benchmark(
                id="juice-shop",
                name="OWASP Juice Shop",
                target_type="spa",
                known_vulnerabilities=[BenchmarkVulnerability(id="sqli-1", name="SQLi", severity="high")],
            )
        ],
        benchmarks_path,
    )


def test_log_observation_appends_to_vendor(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "scan", "log-observation",
            "--vendor-id", "v1", "--context", "juice-shop crawl",
            "--note", "UI felt sluggish", "--tags", "ux-friction,setup-cost",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.observations[0].note == "UI felt sluggish"
    assert vendor.observations[0].tags == ["ux-friction", "setup-cost"]


def test_ingest_scan_result_computes_detection_rate(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    findings_file = tmp_path / "findings.json"
    findings_file.write_text(
        json.dumps([{"vuln_id": "sqli-1", "severity": "high"}, {"vuln_id": "not-a-real-vuln", "severity": "low"}])
    )
    result = runner.invoke(
        app,
        [
            "scan", "ingest-scan-result",
            "--vendor-id", "v1", "--benchmark-id", "juice-shop",
            "--file", str(findings_file), "--test-id", "scan-1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "1/1" in result.output
    assert "1 false positive" in result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.hands_on_results[0].benchmark_id == "juice-shop"


def test_ingest_scan_result_errors_on_unknown_benchmark(tmp_path, monkeypatch):
    _setup_vendor_and_benchmark(monkeypatch, tmp_path)
    findings_file = tmp_path / "findings.json"
    findings_file.write_text("[]")
    result = runner.invoke(
        app,
        [
            "scan", "ingest-scan-result",
            "--vendor-id", "v1", "--benchmark-id", "missing-benchmark",
            "--file", str(findings_file), "--test-id", "scan-1",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output
