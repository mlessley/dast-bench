from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()


def test_status_command_reports_no_gaps_on_clean_setup(tmp_path, monkeypatch):
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
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "no gaps found" in result.output


def test_status_command_reports_missing_score(tmp_path, monkeypatch):
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
    result = runner.invoke(app, ["status"])
    assert "missing scores" in result.output


def test_status_command_appends_progress_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "Progress:" in result.output
    assert "[ ] Criteria      not started" in result.output
    assert "Next: run dast-criteria --" in result.output


def test_status_command_existing_gap_report_output_unchanged(tmp_path, monkeypatch):
    # Regression guard: dast-shortlist and dast-report depend on this exact
    # wording. This plan must never change it, only append after it.
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
    result = runner.invoke(app, ["status"])
    assert "v1: missing scores for c1" in result.output
