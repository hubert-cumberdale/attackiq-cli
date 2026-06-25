from __future__ import annotations

from types import TracebackType
from typing import Any, Literal, cast

import pytest

import attackiq_cli.services as services
import attackiq_cli.services_mutations as services_mutations
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

    def send(self, operation: Operation, **kwargs: object) -> _Resp:
        self.calls.append({"operation": operation, **kwargs})
        return _ClientStub._Resp(self.payload)


class _ClientManager:
    def __init__(self, stub: _ClientStub) -> None:
        self.stub = stub

    def __enter__(self) -> _ClientStub:
        return self.stub

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> Literal[False]:
        return False


class _SpecIndex:
    def __init__(self, operation: Operation) -> None:
        self.operation = operation

    def get_operation(self, operation_id: str) -> Operation:
        assert operation_id == self.operation.operation_id
        return self.operation


def _service_context(spec: object) -> services.ServiceContext:
    return services.ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=AuthContext(account_token="token", jwt=None),
        spec=cast(Any, spec),
    )


def test_synthetic_operation_builders_are_reexported() -> None:
    assert services.build_det_pipeline_create_assessment_operation is (
        services_mutations.build_det_pipeline_create_assessment_operation
    )
    assert services.build_scenario_template_upload_operation is (
        services_mutations.build_scenario_template_upload_operation
    )

    create_operation = services.build_det_pipeline_create_assessment_operation()
    assert create_operation.operation_id == "det_pipeline_create_assessment"
    assert create_operation.method == "post"
    assert create_operation.path == "/v1/assessments"
    assert create_operation.security == [{"Account Token": []}, {"JSON Web Token": []}]

    upload_operation = services.build_scenario_template_upload_operation()
    assert upload_operation.operation_id == "scenario_template_upload"
    assert upload_operation.method == "post"
    assert upload_operation.path == "/v1/scenario_templates"
    assert upload_operation.security == [{"Account Token": []}, {"JSON Web Token": []}]


def test_create_assessment_from_scenarios_uses_synthetic_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _ClientStub({"id": "assessment-1"})
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: _ClientManager(stub),
    )

    result = services.create_assessment_from_scenarios(
        _service_context(object()),
        name="Assessment",
        scenario_ids=["scenario-1", "scenario-2"],
        insecure=False,
        timeout=30.0,
        check_auth=False,
    )

    assert result == {"id": "assessment-1"}
    assert stub.calls
    call = stub.calls[0]
    assert cast(Operation, call["operation"]).operation_id == "det_pipeline_create_assessment"
    assert call["path_params"] == {}
    assert call["query_params"] == {}
    assert call["json_body"] == {
        "name": "Assessment",
        "scenario_ids": ["scenario-1", "scenario-2"],
    }


def test_update_assessment_defaults_normalizes_string_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _ClientStub("Updated")
    operation = Operation(
        operation_id="v1_assessments_update_defaults_create",
        method="post",
        path="/v1/assessments/{id}/update_defaults",
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: _ClientManager(stub),
    )

    result = services.update_assessment_defaults(
        _service_context(_SpecIndex(operation)),
        assessment_id="assessment-1",
        assets="asset-1,asset-2",
        asset_groups=None,
        insecure=False,
        timeout=30.0,
        check_auth=False,
    )

    assert result == {"message": "Updated"}
    assert stub.calls
    call = stub.calls[0]
    assert cast(Operation, call["operation"]).operation_id == (
        "v1_assessments_update_defaults_create"
    )
    assert call["path_params"] == {"id": "assessment-1"}
    assert call["json_body"] == {"assets": "asset-1,asset-2"}
