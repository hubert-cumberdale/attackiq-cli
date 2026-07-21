from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from attackiq_cli.mutations import (
    build_dry_run_call_plan,
    run_mutation_command,
    write_apply_response_json,
    write_dry_run_call_plan,
)
from attackiq_cli.spec import Operation


def _operation() -> Operation:
    return Operation(
        operation_id="v1_example_create",
        method="post",
        path="/v1/example",
        summary="Example create",
        parameters=[],
        request_body=None,
        tags=["example"],
        security=[],
    )


def test_build_dry_run_call_plan_omits_empty_body() -> None:
    assert build_dry_run_call_plan(
        operation_id="v1_example_create",
        path_params={"id": "abc"},
    ) == {
        "operation_id": "v1_example_create",
        "path_params": {"id": "abc"},
        "query_params": {},
    }


def test_write_dry_run_call_plan_to_file_reports_path(tmp_path: Path) -> None:
    output = tmp_path / "plans" / "call-plan.json"
    written: list[Path] = []

    write_dry_run_call_plan(
        operation_id="v1_example_create",
        output=output,
        query_params={"page": 1},
        json_body={"name": "Example"},
        on_file_written=written.append,
    )

    assert written == [output]
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "operation_id": "v1_example_create",
        "path_params": {},
        "query_params": {"page": 1},
        "json_body": {"name": "Example"},
    }


def test_write_apply_response_json_does_not_report_file(tmp_path: Path) -> None:
    output = tmp_path / "response.json"

    write_apply_response_json(output, {"ok": True})

    assert json.loads(output.read_text(encoding="utf-8")) == {"ok": True}


def test_run_mutation_command_dry_run_does_not_prepare_apply_context(tmp_path: Path) -> None:
    output = tmp_path / "call-plan.json"

    def prepare_context() -> tuple[object, float | None]:
        raise AssertionError("dry-run should not prepare apply context")

    def apply_request(_context: object, _timeout: float | None) -> Any:
        raise AssertionError("dry-run should not apply")

    run_mutation_command(
        apply=False,
        operation=_operation(),
        output=output,
        prepare_context=prepare_context,
        apply_request=apply_request,
        handle_http_error=lambda _exc: None,
        json_body={"name": "Example"},
    )

    assert json.loads(output.read_text(encoding="utf-8"))["json_body"] == {"name": "Example"}


def test_run_mutation_command_apply_writes_response(tmp_path: Path) -> None:
    output = tmp_path / "response.json"

    run_mutation_command(
        apply=True,
        operation=_operation(),
        output=output,
        prepare_context=lambda: ("context", 10.0),
        apply_request=lambda context, timeout: {"context": context, "timeout": timeout},
        handle_http_error=lambda _exc: None,
    )

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "context": "context",
        "timeout": 10.0,
    }


def test_run_mutation_command_delegates_http_errors(tmp_path: Path) -> None:
    errors: list[str] = []

    def raise_http_error(_context: object, _timeout: float | None) -> Any:
        raise httpx.ConnectError("connection failed")

    run_mutation_command(
        apply=True,
        operation=_operation(),
        output=tmp_path / "response.json",
        prepare_context=lambda: (object(), None),
        apply_request=raise_http_error,
        handle_http_error=lambda exc: errors.append(str(exc)),
    )

    assert errors == ["connection failed"]
