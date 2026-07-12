from typer.testing import CliRunner

from core import storage
from core.cli import app

runner = CliRunner()

ADD_ARGS = ["benchmark", "add", "--id", "juice-shop", "--name", "OWASP Juice Shop", "--target-type", "spa"]


def test_add_benchmark_then_list_shows_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["benchmark", "list"])
    assert "juice-shop" in result.output
    assert "OWASP Juice Shop" in result.output
    assert "known_vulnerabilities=0" in result.output


def test_add_benchmark_rejects_duplicate_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_add_vulnerability_appends_to_benchmark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(
        app,
        [
            "benchmark", "add-vulnerability",
            "--benchmark-id", "juice-shop", "--vuln-id", "40018",
            "--name", "SQL Injection", "--severity", "high",
        ],
    )
    assert result.exit_code == 0, result.output
    benchmarks = storage.load_benchmarks(tmp_path / "data" / "benchmarks.yaml")
    assert benchmarks[0].known_vulnerabilities[0].id == "40018"
    result = runner.invoke(app, ["benchmark", "list"])
    assert "known_vulnerabilities=1" in result.output


def test_add_vulnerability_errors_on_unknown_benchmark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "benchmark", "add-vulnerability",
            "--benchmark-id", "missing", "--vuln-id", "40018",
            "--name", "SQL Injection", "--severity", "high",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_add_vulnerability_rejects_duplicate_vuln_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    vuln_args = [
        "benchmark", "add-vulnerability",
        "--benchmark-id", "juice-shop", "--vuln-id", "40018",
        "--name", "SQL Injection", "--severity", "high",
    ]
    runner.invoke(app, vuln_args)
    result = runner.invoke(app, vuln_args)
    assert result.exit_code != 0
    assert "already exists" in result.output
