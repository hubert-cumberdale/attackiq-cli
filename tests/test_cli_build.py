import json

from typer.testing import CliRunner

from attackiq_cli import cli


def test_build_assessment_from_template_writes_body_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "build",
            "assessment",
            "from-template",
            "--template-id",
            "d09d29ba-eed8-4212-bff2-4d1ee11ed80c",
            "--name",
            "Test Assessment",
            "--blueprint-id",
            "ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["template"] == "d09d29ba-eed8-4212-bff2-4d1ee11ed80c"
    assert payload["project_name"] == "Test Assessment"
    assert payload["blueprint"] == "ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796"


def test_build_test_create_writes_body_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "build",
            "test",
            "create",
            "--assessment-id",
            "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
            "--name",
            "API Test",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["project"] == "ef900dfe-1bb9-475d-944a-07ffaeb26ad4"
    assert payload["name"] == "API Test"


def test_build_test_add_scenarios_writes_body_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "build",
            "test",
            "add-scenarios",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--scenario-id",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--scenario-id",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--scenario-id",
            "00000000-0000-0000-0000-000000000000",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["include"] == [
        "03fef867-3227-4d47-a858-90f9ad8cf217",
        "00000000-0000-0000-0000-000000000000",
    ]
