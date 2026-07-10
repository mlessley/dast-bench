from pathlib import Path

from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


def _seed_scored_vendor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(
        app,
        [
            "criteria", "add-criterion",
            "--id", "c1", "--category", "Coverage", "--name", "n",
            "--description", "d", "--weight", "100", "--rubric", "r",
        ],
    )
    runner.invoke(app, ["candidate", "add", "--id", "v1", "--name", "Vendor One", "--source", "discovered"])


def test_render_command_writes_all_report_formats(tmp_path, monkeypatch):
    _seed_scored_vendor(tmp_path, monkeypatch)
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    result = runner.invoke(app, ["render"])
    assert result.exit_code == 0, result.output
    assert (Path("reports") / "scorecard-v1.md").exists()
    assert (Path("reports") / "comparison-matrix.md").exists()
    assert (Path("reports") / "comparison-matrix.xlsx").exists()
    assert (Path("reports") / "dashboard.html").exists()


def test_render_command_surfaces_gap_warnings(tmp_path, monkeypatch):
    _seed_scored_vendor(tmp_path, monkeypatch)
    result = runner.invoke(app, ["render"])
    assert "missing scores" in result.output
