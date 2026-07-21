from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import TEST_FIELD_ORDER, write_csv_records, write_json
from attackiq_cli.mutation_plans import (
    build_add_scenarios_to_test_plan,
    build_create_test_plan,
    build_get_test_status_plan,
)
from attackiq_cli.mutations import run_mutation_command
from attackiq_cli.services import (
    ServiceContext,
    TestFilters,
    build_auth_context,
    build_test_query_params,
    build_test_summary_records,
    ensure_auth,
    fetch_test_detail,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import add_scenarios_to_test as svc_add_scenarios_to_test
from attackiq_cli.services import build_client as build_client
from attackiq_cli.services import create_test as svc_create_test
from attackiq_cli.services import get_test_status as svc_get_test_status
from attackiq_cli.services import list_tests as svc_list_tests
from attackiq_cli.spec import Operation, SpecIndex

console = Console()

tests_app = typer.Typer(
    help="Test commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "TestFilters",
    "add_test_scenarios",
    "build_client",
    "create_test",
    "get_test_status",
    "list_tests",
    "show_test",
    "tests_app",
]


def warn_if_insecure(base_url: str) -> None:
    if warn_if_insecure_base_url(base_url):
        console.print("[yellow]Warning: Base URL uses http:// (TLS disabled).[/yellow]")


def _format_http_error_message(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Request failed ({exc.response.status_code}): {exc}"
    if isinstance(exc, httpx.TimeoutException):
        return f"Request timed out: {exc}"
    if isinstance(exc, httpx.ConnectError):
        return f"Network connection failed: {exc}"
    if isinstance(exc, httpx.RequestError):
        return f"Request failed: {exc}"
    return f"HTTP error: {exc}"


def _print_http_error_and_exit(exc: httpx.HTTPError) -> None:
    message = _format_http_error_message(exc)
    hint = None
    if isinstance(exc, httpx.ConnectError):
        hint = "Check network/DNS access and ATTACKIQ_BASE_URL."
    elif isinstance(exc, httpx.TimeoutException):
        hint = "Try increasing --timeout or check network latency."

    console.print(f"[red]{message}[/red]")
    if hint:
        console.print(f"[yellow]{hint}[/yellow]")
    raise typer.Exit(code=1) from exc


def _normalize_uuid(value: str, *, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise typer.BadParameter(f"{label} is required.")
    try:
        uuid.UUID(cleaned)
    except ValueError as exc:
        raise typer.BadParameter(f"{label} must be a UUID.") from exc
    return cleaned


def _load_uuid_list_from_text(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        parts = [item.strip() for item in cleaned.split(",") if item.strip()]
        items.extend(parts)
    return items


def _load_uuid_list_from_file(path: Path) -> list[str]:
    return _load_uuid_list_from_text(path.read_text(encoding="utf-8"))


def _stable_dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _run_mutation_command(
    ctx: typer.Context,
    *,
    apply: bool,
    operation: Operation,
    output: Path | None,
    timeout: float | None,
    apply_request: Callable[[ServiceContext, float | None], Any],
    index: SpecIndex | None = None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> None:
    run_mutation_command(
        apply=apply,
        operation=operation,
        output=output,
        prepare_context=lambda: _prepare_apply_context(
            ctx,
            operation=operation,
            timeout=timeout,
            index=index,
        ),
        apply_request=apply_request,
        handle_http_error=_print_http_error_and_exit,
        path_params=path_params,
        query_params=query_params,
        json_body=json_body,
        on_dry_run_file_written=lambda path: console.print(f"Response written to {path}"),
    )


def _prepare_apply_context(
    ctx: typer.Context,
    *,
    operation: Operation,
    timeout: float | None,
    index: SpecIndex | None = None,
) -> tuple[ServiceContext, float | None]:
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    try:
        warnings = ensure_auth(operation, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    if index is None:
        index = SpecIndex.from_file(ctx.obj["spec_path"])
    return ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index), timeout


@tests_app.command("list")
def list_tests(
    ctx: typer.Context,
    output_format: Annotated[
        str,
        typer.Option("--output-format", help="Output format: json or csv."),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    page: Annotated[
        int | None,
        typer.Option("--page", help="Page number within results."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
    ] = 200,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Filter by exact test name."),
    ] = None,
    project_template_test_id: Annotated[
        str | None,
        typer.Option(
            "--project-template-test-id",
            help="Filter by project template test UUID.",
        ),
    ] = None,
    run_in_hosted_agent_preferably: Annotated[
        bool | None,
        typer.Option(
            "--run-in-hosted-agent-preferably/--no-run-in-hosted-agent-preferably",
            help="Filter by hosted-agent preference.",
        ),
    ] = None,
    use_hosted_agent: Annotated[
        bool | None,
        typer.Option(
            "--use-hosted-agent/--no-use-hosted-agent",
            help="Filter by use_hosted_agent.",
        ),
    ] = None,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if page is not None and page < 1:
        raise typer.BadParameter("page must be >= 1.")

    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")
    if fmt == "csv" and output is None:
        raise typer.BadParameter("CSV output requires --output.")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)

    filters = TestFilters(
        name=name,
        project_template_test_id=project_template_test_id,
        run_in_hosted_agent_preferably=run_in_hosted_agent_preferably,
        use_hosted_agent=use_hosted_agent,
    )
    query_params = build_test_query_params(filters)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        items = svc_list_tests(
            context,
            page=page,
            page_size=page_size,
            query_params=query_params or None,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    if fmt == "json":
        if output is None:
            write_json(sys.stdout, items)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, items)
        return

    if output is None:
        raise typer.BadParameter("CSV output requires --output.")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = build_test_summary_records(items)
    write_csv_records(output, records, preferred_fields=TEST_FIELD_ORDER)


@tests_app.command("show")
def show_test(
    ctx: typer.Context,
    test_id: Annotated[str, typer.Argument(help="Test UUID.")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_retrieve")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        detail = fetch_test_detail(
            context,
            test_id=test_id,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    if output is None:
        write_json(sys.stdout, detail)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, detail)


@tests_app.command("create")
def create_test(
    ctx: typer.Context,
    assessment_id: Annotated[
        str,
        typer.Option("--assessment-id", help="Assessment UUID."),
    ],
    name: Annotated[str, typer.Option("--name", help="Test name.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
        ),
    ] = None,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    test_name = (name or "").strip()
    if not test_name:
        raise typer.BadParameter("--name is required.")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    plan = build_create_test_plan(
        index,
        assessment_id=_normalize_uuid(assessment_id, label="--assessment-id"),
        name=test_name,
    )
    body = cast(dict[str, Any], plan.json_body)

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        index=index,
        json_body=plan.json_body,
        apply_request=lambda context, effective_timeout: svc_create_test(
            context,
            assessment_id=body["project"],
            name=body["name"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@tests_app.command("add-scenarios")
def add_test_scenarios(
    ctx: typer.Context,
    test_id: Annotated[str, typer.Argument(help="Test UUID.")],
    scenario_id: Annotated[
        list[str] | None,
        typer.Option("--scenario-id", help="Scenario UUID to include (repeatable)."),
    ] = None,
    scenario_ids_file: Annotated[
        Path | None,
        typer.Option(
            "--scenario-ids-file",
            exists=True,
            readable=True,
            help="Text file containing scenario UUIDs (one per line or comma-separated).",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
        ),
    ] = None,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    requested: list[str] = []
    requested.extend([value for value in scenario_id or [] if value and value.strip()])
    if scenario_ids_file is not None:
        requested.extend(_load_uuid_list_from_file(scenario_ids_file))
    requested = _stable_dedup([value.strip() for value in requested if value.strip()])
    if not requested:
        raise typer.BadParameter("At least one --scenario-id (or --scenario-ids-file) is required.")

    index = SpecIndex.from_file(ctx.obj["spec_path"])
    plan = build_add_scenarios_to_test_plan(
        index,
        test_id=_normalize_uuid(test_id, label="test-id"),
        scenario_ids=[_normalize_uuid(value, label="scenario-id") for value in requested],
    )
    body = cast(dict[str, Any], plan.json_body)

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=plan.path_params,
        json_body=plan.json_body,
        apply_request=lambda context, effective_timeout: svc_add_scenarios_to_test(
            context,
            test_id=plan.path_params["id"],
            scenario_ids=body["include"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@tests_app.command("get-status")
def get_test_status(
    ctx: typer.Context,
    test_id: Annotated[str, typer.Argument(help="Test UUID.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
        ),
    ] = None,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    plan = build_get_test_status_plan(
        index,
        test_id=_normalize_uuid(test_id, label="test-id"),
    )

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=plan.path_params,
        query_params=plan.query_params,
        apply_request=lambda context, effective_timeout: svc_get_test_status(
            context,
            test_id=plan.path_params["id"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )
