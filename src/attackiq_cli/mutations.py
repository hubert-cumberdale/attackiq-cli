from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO, TypeVar

import httpx

from attackiq_cli.exporter import write_json
from attackiq_cli.spec import Operation

ContextT = TypeVar("ContextT")


def build_dry_run_call_plan(
    *,
    operation_id: str,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operation_id": operation_id,
        "path_params": path_params or {},
        "query_params": query_params or {},
    }
    if json_body is not None:
        payload["json_body"] = json_body
    return payload


def write_json_payload(
    output: Path | None,
    payload: Any,
    *,
    stdout: TextIO | None = None,
    on_file_written: Callable[[Path], None] | None = None,
) -> None:
    if output is None:
        write_json(stdout or sys.stdout, payload)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, payload)
    if on_file_written is not None:
        on_file_written(output)


def write_dry_run_call_plan(
    *,
    operation_id: str,
    output: Path | None = None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    stdout: TextIO | None = None,
    on_file_written: Callable[[Path], None] | None = None,
) -> None:
    write_json_payload(
        output,
        build_dry_run_call_plan(
            operation_id=operation_id,
            path_params=path_params,
            query_params=query_params,
            json_body=json_body,
        ),
        stdout=stdout,
        on_file_written=on_file_written,
    )


def write_apply_response_json(
    output: Path | None,
    payload: Any,
    *,
    stdout: TextIO | None = None,
) -> None:
    write_json_payload(output, payload, stdout=stdout)


def run_mutation_command(
    *,
    apply: bool,
    operation: Operation,
    output: Path | None,
    prepare_context: Callable[[], tuple[ContextT, float | None]],
    apply_request: Callable[[ContextT, float | None], Any],
    handle_http_error: Callable[[httpx.HTTPError], None],
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    on_dry_run_file_written: Callable[[Path], None] | None = None,
) -> None:
    if not apply:
        write_dry_run_call_plan(
            operation_id=operation.operation_id,
            output=output,
            path_params=path_params,
            query_params=query_params,
            json_body=json_body,
            on_file_written=on_dry_run_file_written,
        )
        return

    try:
        context, effective_timeout = prepare_context()
        response = apply_request(context, effective_timeout)
    except httpx.HTTPError as exc:
        handle_http_error(exc)
        return

    write_apply_response_json(output, response)
