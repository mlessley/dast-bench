from typer.testing import CliRunner

from core.cli import app

runner = CliRunner()

ADD_ARGS = [
    "criteria",
    "add-criterion",
    "--id",
    "c1",
    "--category",
    "Coverage",
    "--name",
    "API Coverage",
    "--description",
    "Detects vulnerabilities in REST/GraphQL APIs",
    "--weight",
    "20",
    "--rubric",
    "5 = full OpenAPI-driven scanning",
]


def test_add_criterion_then_list_shows_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "c1" in result.output
    assert "API Coverage" in result.output


def test_add_criterion_rejects_duplicate_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_set_weight_updates_existing_criterion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "set-weight", "--id", "c1", "--weight", "30"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["criteria", "list"])
    assert "weight=30" in result.output


def test_set_weight_errors_on_unknown_criterion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["criteria", "set-weight", "--id", "missing", "--weight", "10"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_list_warns_when_weights_do_not_sum_to_100(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "list"])
    assert "warning" in result.output.lower()


def test_remove_criterion_removes_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "remove-criterion", "--id", "c1"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "c1" not in result.output


def test_remove_criterion_errors_on_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["criteria", "remove-criterion", "--id", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_remove_criterion_warns_about_orphaned_scores(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    runner.invoke(app, ["candidate", "add", "--id", "v1", "--name", "Vendor One", "--source", "discovered"])
    runner.invoke(
        app,
        [
            "candidate", "record-score",
            "--vendor-id", "v1", "--criterion-id", "c1",
            "--score", "4", "--evidence", "docs", "--confidence", "paper",
        ],
    )
    result = runner.invoke(app, ["criteria", "remove-criterion", "--id", "c1"])
    assert result.exit_code == 0, result.output
    assert "1 vendor" in result.output
    assert "orphaned" in result.output


def test_update_criterion_changes_only_passed_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "update-criterion", "--id", "c1", "--name", "New Name"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "New Name" in result.output
    assert "weight=20" in result.output


def test_update_criterion_updates_weight(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ADD_ARGS)
    result = runner.invoke(app, ["criteria", "update-criterion", "--id", "c1", "--weight", "75"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["criteria", "list"])
    assert "weight=75" in result.output


def test_update_criterion_errors_on_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["criteria", "update-criterion", "--id", "missing", "--name", "x"])
    assert result.exit_code != 0
    assert "not found" in result.output
