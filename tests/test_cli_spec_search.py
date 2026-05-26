from __future__ import annotations

from typer.testing import CliRunner

from attackiq_cli import cli
from attackiq_cli.spec import Operation


def _operation() -> Operation:
    return Operation(
        operation_id="list_scenarios",
        method="get",
        path="/v1/scenarios",
        summary="Retrieve scenarios",
        parameters=[],
        request_body=None,
        tags=["scenarios"],
        security=[],
    )


def test_spec_search_outputs_results(monkeypatch):
    class DummySpecIndex:
        def search_operations(self, query: str, tag: str | None = None) -> list[Operation]:
            assert query == "scenario"
            assert tag == "scenarios"
            return [_operation()]

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())

    runner = CliRunner()
    result = runner.invoke(cli.app, ["spec", "search", "scenario", "--tag", "scenarios"])

    assert result.exit_code == 0
    assert "list_scenarios" in result.output


def test_spec_search_limits_and_offsets_results(monkeypatch):
    operations = [
        _operation(),
        Operation(
            operation_id="list_assessments",
            method="get",
            path="/v1/assessments",
            summary="Retrieve assessments",
            parameters=[],
            request_body=None,
            tags=["assessments"],
            security=[],
        ),
    ]

    class DummySpecIndex:
        def search_operations(self, query: str, tag: str | None = None) -> list[Operation]:
            assert query == "list"
            assert tag is None
            return operations

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["spec", "search", "list", "--limit", "1", "--offset", "1"],
    )

    assert result.exit_code == 0
    assert "list_scenarios" not in result.output
    assert "list_assessments" in result.output


def test_spec_search_fields_selection(monkeypatch):
    class DummySpecIndex:
        def search_operations(self, query: str, tag: str | None = None) -> list[Operation]:
            assert query == "scenario"
            assert tag is None
            return [_operation()]

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["spec", "search", "scenario", "--fields", "operation_id,method"],
    )

    assert result.exit_code == 0
    assert "OperationId" in result.output
    assert "Method" in result.output
    assert "Path" not in result.output
    assert "Summary" not in result.output
