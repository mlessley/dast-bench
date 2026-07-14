import json

from typer.testing import CliRunner

from core import storage
from core.cli import app

runner = CliRunner()


def _add_vendor(monkeypatch, tmp_path, vendor_id="veracode"):
    monkeypatch.chdir(tmp_path)
    return runner.invoke(app, ["candidate", "add", "--id", vendor_id, "--name", "Veracode", "--source", "seeded"])


def _add_criterion(criterion_id="aspm-integration"):
    return runner.invoke(
        app,
        [
            "criteria", "add-criterion",
            "--id", criterion_id, "--category", "Reporting & Extensibility", "--name", "n",
            "--description", "d", "--weight", "100", "--rubric", "r",
        ],
    )


def _write_findings_file(tmp_path, findings):
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(findings))
    return path


def test_cache_record_then_show_round_trips(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(
        tmp_path, [{"url": "veracode.com/risk-manager", "snippet": "ASPM platform"}]
    )
    result = runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--query", "Veracode Risk Manager ASPM",
            "--findings-file", str(findings_file),
        ],
    )
    assert result.exit_code == 0, result.output

    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    entry = cache.criteria["aspm-integration"]
    assert entry.queries == ["Veracode Risk Manager ASPM"]
    assert entry.findings[0].url == "veracode.com/risk-manager"
    assert entry.stale is False

    result = runner.invoke(app, ["cache", "show", "--vendor-id", "veracode"])
    assert result.exit_code == 0, result.output
    assert "aspm-integration" in result.output
    assert "veracode.com/risk-manager" in result.output


def test_cache_record_rejects_malformed_findings_file(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = tmp_path / "bad.json"
    findings_file.write_text("not json")
    result = runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    assert result.exit_code != 0
    assert "invalid JSON" in result.output


def test_cache_show_errors_when_no_cache_exists(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(app, ["cache", "show", "--vendor-id", "veracode"])
    assert result.exit_code != 0
    assert "no research cache found" in result.output


def test_cache_invalidate_single_criterion(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    result = runner.invoke(
        app, ["cache", "invalidate", "--vendor-id", "veracode", "--criterion-id", "aspm-integration"]
    )
    assert result.exit_code == 0, result.output
    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    assert cache.criteria["aspm-integration"].stale is True


def test_cache_invalidate_by_max_score(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    _add_criterion("aspm-integration")
    _add_criterion("detection-accuracy")
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--score", "2.0", "--evidence", "low score", "--confidence", "paper",
        ],
    )
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "veracode", "--criterion-id", "detection-accuracy",
            "--score", "4.5", "--evidence", "high score", "--confidence", "paper",
        ],
    )
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "detection-accuracy",
            "--findings-file", str(findings_file),
        ],
    )

    result = runner.invoke(
        app, ["cache", "invalidate", "--vendor-id", "veracode", "--max-score", "2.5"]
    )
    assert result.exit_code == 0, result.output
    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    assert cache.criteria["aspm-integration"].stale is True
    assert cache.criteria["detection-accuracy"].stale is False


def test_cache_invalidate_all(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "detection-accuracy",
            "--findings-file", str(findings_file),
        ],
    )
    result = runner.invoke(app, ["cache", "invalidate", "--vendor-id", "veracode", "--all"])
    assert result.exit_code == 0, result.output
    cache = storage.load_research_cache(
        tmp_path / "data" / "research-cache" / "veracode.yaml", "veracode"
    )
    assert all(entry.stale for entry in cache.criteria.values())


def test_cache_invalidate_requires_exactly_one_mode(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    findings_file = _write_findings_file(tmp_path, [])
    runner.invoke(
        app,
        [
            "cache", "record",
            "--vendor-id", "veracode", "--criterion-id", "aspm-integration",
            "--findings-file", str(findings_file),
        ],
    )
    result = runner.invoke(app, ["cache", "invalidate", "--vendor-id", "veracode"])
    assert result.exit_code != 0
    assert "exactly one" in result.output
