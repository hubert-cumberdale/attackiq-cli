from __future__ import annotations

import json
from typing import Any, Literal, cast

import pytest
from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.services as services
from attackiq_cli.client import AuthContext
from attackiq_cli.config import CliConfig
from attackiq_cli.spec import Operation


class _ClientStub:
    def __init__(self, payload: object | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.payload = {"ok": True} if payload is None else payload

    class _Resp:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def json(self) -> object:
            return self._payload

    def send(self, operation: Operation, **kwargs: Any):
        self.calls.append({"operation": operation, **kwargs})
        return _ClientStub._Resp(self.payload)


class _ClientManager:
    def __init__(self, stub: _ClientStub) -> None:
        self.stub = stub

    def __enter__(self) -> _ClientStub:
        return self.stub

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False


class _DryRunSpecIndex:
    def get_operation(self, operation_id: str) -> Operation:
        return Operation(
            operation_id=operation_id,
            method="post",
            path="/fixture",
            summary="",
            parameters=[],
            request_body=None,
            tags=[],
            security=[],
        )


def test_assessments_create_dry_run_outputs_call_plan(monkeypatch) -> None:
    # Ensure no network path is used.
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "create",
            "--name",
            " My Assessment ",
            "--scenario-id",
            "00000000-0000-0000-0000-000000000000",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "operation_id": "det_pipeline_create_assessment",
        "path_params": {},
        "query_params": {},
        "json_body": {
            "name": "My Assessment",
            "scenario_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    }


@pytest.mark.parametrize(
    ("args", "operation_id"),
    [
        (
            [
                "assessments",
                "create",
                "--name",
                "My Assessment",
                "--scenario-id",
                "00000000-0000-0000-0000-000000000000",
            ],
            "det_pipeline_create_assessment",
        ),
        (
            [
                "assessments",
                "create-from-template",
                "--template-id",
                "d09d29ba-eed8-4212-bff2-4d1ee11ed80c",
                "--name",
                "Template Assessment",
            ],
            "v1_assessments_project_from_template_create",
        ),
        (
            [
                "assessments",
                "update-defaults",
                "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
                "--asset-id",
                "b77596ec-e4bf-418f-ae33-520555a6105a",
            ],
            "v1_assessments_update_defaults_create",
        ),
        (
            [
                "assessments",
                "run",
                "03fef867-3227-4d47-a858-90f9ad8cf217",
            ],
            "v1_assessments_run_all_create",
        ),
        (
            [
                "tests",
                "create",
                "--assessment-id",
                "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
                "--name",
                "API Test",
            ],
            "v1_tests_create",
        ),
        (
            [
                "tests",
                "add-scenarios",
                "03fef867-3227-4d47-a858-90f9ad8cf217",
                "--scenario-id",
                "00000000-0000-0000-0000-000000000000",
            ],
            "v1_tests_bulk_add_scenarios_create",
        ),
        (
            [
                "tests",
                "get-status",
                "03fef867-3227-4d47-a858-90f9ad8cf217",
            ],
            "v1_tests_get_status_retrieve",
        ),
    ],
)
def test_mutation_dry_run_writes_call_plan_to_output_file(
    tmp_path,
    monkeypatch,
    args,
    operation_id,
) -> None:
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: _DryRunSpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    output = tmp_path / "call-plan.json"

    result = CliRunner().invoke(cli.app, [*args, "--output", str(output)])

    assert result.exit_code == 0, result.stdout
    assert "Response written to" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["operation_id"] == operation_id
    assert payload["path_params"] is not None
    assert payload["query_params"] is not None


def test_assessments_create_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "create",
            "--apply",
            "--name",
            "My Assessment",
            "--scenario-id",
            "00000000-0000-0000-0000-000000000000",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert call["json_body"] == {
        "name": "My Assessment",
        "scenario_ids": ["00000000-0000-0000-0000-000000000000"],
    }


def test_assessments_create_from_template_dry_run_outputs_call_plan(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_project_from_template_create"
            return Operation(
                operation_id="v1_assessments_project_from_template_create",
                method="post",
                path="/v1/assessments/project_from_template",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "create-from-template",
            "--template-id",
            "d09d29ba-eed8-4212-bff2-4d1ee11ed80c",
            "--name",
            " Test Assessment ",
            "--blueprint-id",
            "ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "operation_id": "v1_assessments_project_from_template_create",
        "path_params": {},
        "query_params": {},
        "json_body": {
            "template": "d09d29ba-eed8-4212-bff2-4d1ee11ed80c",
            "project_name": "Test Assessment",
            "blueprint": "ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796",
        },
    }


def test_assessments_create_from_template_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_project_from_template_create"
            return Operation(
                operation_id="v1_assessments_project_from_template_create",
                method="post",
                path="/v1/assessments/project_from_template",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "create-from-template",
            "--apply",
            "--template-id",
            "d09d29ba-eed8-4212-bff2-4d1ee11ed80c",
            "--name",
            "Test Assessment",
            "--blueprint-id",
            "ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert (
        cast(Operation, call["operation"]).operation_id
        == "v1_assessments_project_from_template_create"
    )
    assert call["json_body"] == {
        "template": "d09d29ba-eed8-4212-bff2-4d1ee11ed80c",
        "project_name": "Test Assessment",
        "blueprint": "ee15c9ab-2dbc-4d3f-9b86-35c00d0d1796",
    }


def test_assessments_update_defaults_dry_run_outputs_call_plan(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_update_defaults_create"
            return Operation(
                operation_id="v1_assessments_update_defaults_create",
                method="post",
                path="/v1/assessments/{id}/update_defaults",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "update-defaults",
            "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
            "--asset-id",
            "b77596ec-e4bf-418f-ae33-520555a6105a",
            "--asset-id",
            "b77596ec-e4bf-418f-ae33-520555a6105a",
            "--asset-id",
            "5d987e7d-91da-43d2-9e99-f346472e5cfc",
            "--asset-group-id",
            "ae91d780-e438-4208-af68-c9c72ae66f93",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "operation_id": "v1_assessments_update_defaults_create",
        "path_params": {"id": "ef900dfe-1bb9-475d-944a-07ffaeb26ad4"},
        "query_params": {},
        "json_body": {
            "assets": (
                "b77596ec-e4bf-418f-ae33-520555a6105a,"
                "5d987e7d-91da-43d2-9e99-f346472e5cfc"
            ),
            "asset_groups": "ae91d780-e438-4208-af68-c9c72ae66f93",
        },
    }


def test_assessments_update_defaults_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_update_defaults_create"
            return Operation(
                operation_id="v1_assessments_update_defaults_create",
                method="post",
                path="/v1/assessments/{id}/update_defaults",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "update-defaults",
            "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
            "--apply",
            "--asset-id",
            "b77596ec-e4bf-418f-ae33-520555a6105a",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert (
        cast(Operation, call["operation"]).operation_id
        == "v1_assessments_update_defaults_create"
    )
    assert call["path_params"] == {"id": "ef900dfe-1bb9-475d-944a-07ffaeb26ad4"}
    assert call["json_body"] == {"assets": "b77596ec-e4bf-418f-ae33-520555a6105a"}


def test_assessments_update_defaults_requires_assets(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "update-defaults",
            "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
        ],
    )

    assert result.exit_code == 2
    assert "update-defaults" in result.output


def test_tests_create_dry_run_outputs_call_plan(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_create"
            return Operation(
                operation_id="v1_tests_create",
                method="post",
                path="/v1/tests",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "tests",
            "create",
            "--assessment-id",
            "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
            "--name",
            " API Test ",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "operation_id": "v1_tests_create",
        "path_params": {},
        "query_params": {},
        "json_body": {"project": "ef900dfe-1bb9-475d-944a-07ffaeb26ad4", "name": "API Test"},
    }


def test_tests_create_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_create"
            return Operation(
                operation_id="v1_tests_create",
                method="post",
                path="/v1/tests",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "tests",
            "create",
            "--apply",
            "--assessment-id",
            "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
            "--name",
            "API Test",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert call["json_body"] == {
        "project": "ef900dfe-1bb9-475d-944a-07ffaeb26ad4",
        "name": "API Test",
    }


def test_tests_add_scenarios_dry_run_outputs_call_plan(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_bulk_add_scenarios_create"
            return Operation(
                operation_id="v1_tests_bulk_add_scenarios_create",
                method="post",
                path="/v1/tests/{id}/bulk_add_scenarios",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "tests",
            "add-scenarios",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--scenario-id",
            "00000000-0000-0000-0000-000000000000",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "operation_id": "v1_tests_bulk_add_scenarios_create",
        "path_params": {"id": "03fef867-3227-4d47-a858-90f9ad8cf217"},
        "query_params": {},
        "json_body": {"include": ["00000000-0000-0000-0000-000000000000"]},
    }


def test_tests_add_scenarios_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_bulk_add_scenarios_create"
            return Operation(
                operation_id="v1_tests_bulk_add_scenarios_create",
                method="post",
                path="/v1/tests/{id}/bulk_add_scenarios",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "tests",
            "add-scenarios",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--apply",
            "--scenario-id",
            "00000000-0000-0000-0000-000000000000",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert call["path_params"] == {"id": "03fef867-3227-4d47-a858-90f9ad8cf217"}
    assert call["json_body"] == {"include": ["00000000-0000-0000-0000-000000000000"]}


def test_tests_add_scenarios_apply_normalizes_string_response(monkeypatch) -> None:
    stub = _ClientStub("Successfully added all scenarios")

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_bulk_add_scenarios_create"
            return Operation(
                operation_id="v1_tests_bulk_add_scenarios_create",
                method="post",
                path="/v1/tests/{id}/bulk_add_scenarios",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))
    context = services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=AuthContext(account_token="token", jwt=None),
        spec=cast(Any, DummySpecIndex()),
    )

    result = services.add_scenarios_to_test(
        context,
        test_id="03fef867-3227-4d47-a858-90f9ad8cf217",
        scenario_ids=["00000000-0000-0000-0000-000000000000"],
        insecure=False,
        timeout=30.0,
        check_auth=False,
    )

    assert result == {"message": "Successfully added all scenarios"}
    assert stub.calls


def test_typer_tracebacks_hide_locals() -> None:
    assert cli.app.pretty_exceptions_show_locals is False
    assert cli.tests_app.pretty_exceptions_show_locals is False


def test_assessments_run_dry_run_outputs_call_plan(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_run_all_create"
            return Operation(
                operation_id="v1_assessments_run_all_create",
                method="post",
                path="/v1/assessments/{id}/run_all",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    result = runner.invoke(cli.app, ["assessments", "run", "03fef867-3227-4d47-a858-90f9ad8cf217"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["operation_id"] == "v1_assessments_run_all_create"
    assert payload["path_params"] == {"id": "03fef867-3227-4d47-a858-90f9ad8cf217"}
    assert payload["query_params"] == {}
    assert "json_body" not in payload


def test_assessments_run_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_assessments_run_all_create"
            return Operation(
                operation_id="v1_assessments_run_all_create",
                method="post",
                path="/v1/assessments/{id}/run_all",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "assessments",
            "run",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert cast(Operation, call["operation"]).operation_id == "v1_assessments_run_all_create"
    assert call["path_params"] == {"id": "03fef867-3227-4d47-a858-90f9ad8cf217"}


def test_tests_get_status_dry_run_outputs_call_plan(monkeypatch) -> None:
    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_get_status_retrieve"
            return Operation(
                operation_id="v1_tests_get_status_retrieve",
                method="get",
                path="/v1/tests/{id}/get_status",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        cli,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    result = runner.invoke(cli.app, ["tests", "get-status", "03fef867-3227-4d47-a858-90f9ad8cf217"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["operation_id"] == "v1_tests_get_status_retrieve"
    assert payload["path_params"] == {"id": "03fef867-3227-4d47-a858-90f9ad8cf217"}
    assert payload["query_params"] == {}
    assert "json_body" not in payload


def test_tests_get_status_apply_sends_request(monkeypatch) -> None:
    stub = _ClientStub()

    class DummySpecIndex:
        def get_operation(self, operation_id: str) -> Operation:
            assert operation_id == "v1_tests_get_status_retrieve"
            return Operation(
                operation_id="v1_tests_get_status_retrieve",
                method="get",
                path="/v1/tests/{id}/get_status",
                summary="",
                parameters=[],
                request_body=None,
                tags=[],
                security=[],
            )

    monkeypatch.setattr(cli.SpecIndex, "from_file", lambda *_args, **_kwargs: DummySpecIndex())
    monkeypatch.setattr(cli, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(cli, "resolve_base_url", lambda *_args, **_kwargs: "https://api.example.com")
    monkeypatch.setattr(cli, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cli, "ensure_auth", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(services, "build_client", lambda *_args, **_kwargs: _ClientManager(stub))

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "tests",
            "get-status",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert stub.calls
    call = stub.calls[0]
    assert cast(Operation, call["operation"]).operation_id == "v1_tests_get_status_retrieve"
    assert call["path_params"] == {"id": "03fef867-3227-4d47-a858-90f9ad8cf217"}
