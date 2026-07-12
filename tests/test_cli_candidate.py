from typer.testing import CliRunner

from core import storage
from core.cli import app

runner = CliRunner()


def _add_vendor(monkeypatch, tmp_path, vendor_id="v1", source="discovered"):
    monkeypatch.chdir(tmp_path)
    return runner.invoke(
        app, ["candidate", "add", "--id", vendor_id, "--name", "Vendor One", "--source", source]
    )


def test_add_candidate_then_list_shows_it(tmp_path, monkeypatch):
    result = _add_vendor(monkeypatch, tmp_path)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["candidate", "list"])
    assert "v1" in result.output
    assert "discovered" in result.output


def test_add_candidate_rejects_duplicate_id(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = _add_vendor(monkeypatch, tmp_path)
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_set_status_updates_vendor(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(app, ["candidate", "set-status", "--id", "v1", "--status", "finalist"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["candidate", "list"])
    assert "finalist" in result.output


def test_set_status_errors_on_unknown_vendor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["candidate", "set-status", "--id", "missing", "--status", "finalist"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_record_score_requires_known_criterion(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    assert result.exit_code != 0
    assert "criterion" in result.output.lower()


def test_record_score_stores_score_against_known_criterion(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    runner.invoke(
        app,
        [
            "criteria", "add-criterion",
            "--id", "c1", "--category", "Coverage", "--name", "n",
            "--description", "d", "--weight", "100", "--rubric", "r",
        ],
    )
    result = runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.score_for("c1").score == 4


def test_log_observation_appends_to_vendor(tmp_path, monkeypatch):
    _add_vendor(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "candidate", "log-observation",
            "--vendor-id", "v1", "--context", "juice-shop crawl",
            "--note", "UI felt sluggish", "--tags", "ux-friction,setup-cost",
        ],
    )
    assert result.exit_code == 0, result.output
    vendor = storage.load_vendor(tmp_path / "data" / "candidates" / "v1.yaml")
    assert vendor.observations[0].note == "UI felt sluggish"
    assert vendor.observations[0].tags == ["ux-friction", "setup-cost"]
