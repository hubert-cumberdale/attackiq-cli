from __future__ import annotations

import inspect

import pytest

import attackiq_cli.services_mutations as services_mutations
from attackiq_cli import tui_mutation_preview
from attackiq_cli.mutation_plans import (
    MutationCallPlan,
    build_create_test_plan,
    build_get_test_status_plan,
)
from attackiq_cli.spec import Operation
from attackiq_cli.tui_mutation_preview import (
    REDACTED_VALUE,
    REQUEST_NOT_SENT_STATUS,
    build_tui_mutation_preview,
)


class _Resolver:
    def get_operation(self, operation_id: str) -> Operation:
        return _operation(operation_id=operation_id, method="post", path=f"/fixture/{operation_id}")


def _operation(*, operation_id: str, method: str = "post", path: str = "/fixture") -> Operation:
    return Operation(
        operation_id=operation_id,
        method=method,
        path=path,
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


def test_tui_mutation_preview_renders_supported_call_plan() -> None:
    plan = build_create_test_plan(
        _Resolver(),
        assessment_id="assessment-1",
        name="API Test",
    )

    preview = build_tui_mutation_preview(plan)

    assert preview.as_dict() == {
        "operation_id": "v1_tests_create",
        "method": "POST",
        "path": "/fixture/v1_tests_create",
        "path_params": {},
        "query_params": {},
        "json_body_summary": {"project": "assessment-1", "name": "API Test"},
        "request_status": REQUEST_NOT_SENT_STATUS,
    }


def test_tui_mutation_preview_redacts_and_bounds_body_summary() -> None:
    plan = MutationCallPlan(
        operation=_operation(operation_id="v1_tests_create"),
        json_body={
            "name": "API Test",
            "api_token": "Bearer abcdefghijklmnop",
            "callback_url": "https://tenant.example.test/callback",
            "scenario_ids": [f"scenario-{index}" for index in range(22)],
            "description": "x" * 210,
        },
    )

    preview = build_tui_mutation_preview(plan)
    body = preview.json_body_summary

    assert isinstance(body, dict)
    assert body["name"] == "API Test"
    assert body["api_token"] == REDACTED_VALUE
    assert body["callback_url"] == REDACTED_VALUE
    assert body["scenario_ids"][-1] == "<2 more items>"
    assert body["description"].endswith("...")
    assert len(body["description"]) == 200


def test_tui_mutation_preview_rejects_unsupported_operation() -> None:
    plan = MutationCallPlan(operation=_operation(operation_id="v1_unknown_create"))

    with pytest.raises(ValueError, match="Unsupported TUI mutation preview operation"):
        build_tui_mutation_preview(plan)


def test_tui_mutation_preview_has_no_apply_or_client_path(monkeypatch) -> None:
    monkeypatch.setattr(
        services_mutations,
        "build_client",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no client")),
    )
    plan = build_get_test_status_plan(_Resolver(), test_id="test-1")

    preview = build_tui_mutation_preview(plan)

    assert "apply" not in inspect.signature(build_tui_mutation_preview).parameters
    assert not {
        "AttackIQClient",
        "apply_request",
        "build_client",
        "prepare_context",
    } & set(vars(tui_mutation_preview))
    assert preview.request_status == REQUEST_NOT_SENT_STATUS
    assert preview.as_dict()["path_params"] == {"id": "test-1"}
