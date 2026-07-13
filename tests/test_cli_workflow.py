from typer.testing import CliRunner

from core.cli import app
from core.workflow import SKILLS

runner = CliRunner()


def test_workflow_command_lists_all_six_skills():
    result = runner.invoke(app, ["workflow"])
    assert result.exit_code == 0, result.output
    for skill in SKILLS:
        assert skill["name"] in result.output
        assert skill["purpose"] in result.output
