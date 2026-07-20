from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, NoReturn

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import write_csv_records, write_json
from attackiq_cli.services import (
    ServiceContext,
    ValidationResultFilters,
    build_auth_context,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import (
    fetch_validation_result_executions as svc_fetch_validation_result_executions,
)
from attackiq_cli.services import fetch_validation_results as svc_fetch_validation_results
from attackiq_cli.spec import SpecIndex

console = Console()

validation_results_app = typer.Typer(
    help="Validation result commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "list_validation_result_asset_executions",
    "list_validation_result_scenario_executions",
    "list_validation_results",
    "list_validation_results_by_asset",
    "validation_results_app",
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


def _normalize_output_format(output_format: str) -> str:
    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")
    return fmt


def _validate_records_output_options(output_format: str, output: Path | None) -> str:
    fmt = _normalize_output_format(output_format)
    if fmt == "csv" and output is None:
        raise typer.BadParameter("CSV output requires --output.")
    return fmt


def _write_records_output(
    *,
    records: list[dict[str, Any]],
    output_format: str,
    output: Path | None,
    preferred_fields: tuple[str, ...] | list[str] | None = None,
) -> None:
    fmt = _validate_records_output_options(output_format, output)
    if fmt == "csv":
        if output is None:
            raise AssertionError("CSV output requires a destination path.")
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=preferred_fields)
        return

    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)


def _prepare_read_only_context(
    ctx: typer.Context,
    *,
    insecure: bool,
    timeout: float | None,
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
    if insecure:
        console.print("[yellow]Warning: TLS verification disabled for this request.[/yellow]")

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    return ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index), timeout


def _handle_results_value_error(exc: ValueError) -> NoReturn:
    for line in str(exc).splitlines():
        console.print(f"[red]{line}[/red]")
    raise typer.Exit(code=1) from exc


def _normalize_optional_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_required_path_id(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise typer.BadParameter(f"{label} is required.")
    return cleaned


def _build_validation_result_filters(
    *,
    days: int | None,
    project_ids: str | None,
    scope_id: str | None,
    tag_ids: str | None,
) -> ValidationResultFilters:
    if days is not None and days < 1:
        raise typer.BadParameter("days must be >= 1.")
    return ValidationResultFilters(
        days=days,
        project_ids=_normalize_optional_filter(project_ids),
        scope_id=_normalize_optional_filter(scope_id),
        tag_ids=_normalize_optional_filter(tag_ids),
    )


@validation_results_app.command("list")
def list_validation_results(
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
        int,
        typer.Option("--page", help="Page number within validation results."),
    ] = 1,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
    ] = 200,
    days: Annotated[
        int | None,
        typer.Option("--days", help="Limit results to the last N days."),
    ] = None,
    project_ids: Annotated[
        str | None,
        typer.Option("--project-ids", help="Comma-separated project/assessment IDs filter."),
    ] = None,
    scope_id: Annotated[
        str | None,
        typer.Option("--scope-id", help="Scope ID filter."),
    ] = None,
    tag_ids: Annotated[
        str | None,
        typer.Option("--tag-ids", help="Comma-separated tag IDs filter."),
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
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records, _has_next = svc_fetch_validation_results(
            context,
            by_asset=False,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@validation_results_app.command("by-asset")
def list_validation_results_by_asset(
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
        int,
        typer.Option("--page", help="Page number within validation results."),
    ] = 1,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
    ] = 200,
    days: Annotated[
        int | None,
        typer.Option("--days", help="Limit results to the last N days."),
    ] = None,
    project_ids: Annotated[
        str | None,
        typer.Option("--project-ids", help="Comma-separated project/assessment IDs filter."),
    ] = None,
    scope_id: Annotated[
        str | None,
        typer.Option("--scope-id", help="Scope ID filter."),
    ] = None,
    tag_ids: Annotated[
        str | None,
        typer.Option("--tag-ids", help="Comma-separated tag IDs filter."),
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
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records, _has_next = svc_fetch_validation_results(
            context,
            by_asset=True,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@validation_results_app.command("asset-executions")
def list_validation_result_asset_executions(
    ctx: typer.Context,
    asset_id: Annotated[str, typer.Argument(help="Asset ID.")],
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
    days: Annotated[
        int | None,
        typer.Option("--days", help="Limit results to the last N days."),
    ] = None,
    project_ids: Annotated[
        str | None,
        typer.Option("--project-ids", help="Comma-separated project/assessment IDs filter."),
    ] = None,
    scope_id: Annotated[
        str | None,
        typer.Option("--scope-id", help="Scope ID filter."),
    ] = None,
    tag_ids: Annotated[
        str | None,
        typer.Option("--tag-ids", help="Comma-separated tag IDs filter."),
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
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )
    asset_id = _normalize_required_path_id(asset_id, label="asset_id")

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records = svc_fetch_validation_result_executions(
            context,
            asset_id=asset_id,
            scenario_id=None,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@validation_results_app.command("scenario-executions")
def list_validation_result_scenario_executions(
    ctx: typer.Context,
    scenario_id: Annotated[str, typer.Argument(help="Scenario ID.")],
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
    days: Annotated[
        int | None,
        typer.Option("--days", help="Limit results to the last N days."),
    ] = None,
    project_ids: Annotated[
        str | None,
        typer.Option("--project-ids", help="Comma-separated project/assessment IDs filter."),
    ] = None,
    scope_id: Annotated[
        str | None,
        typer.Option("--scope-id", help="Scope ID filter."),
    ] = None,
    tag_ids: Annotated[
        str | None,
        typer.Option("--tag-ids", help="Comma-separated tag IDs filter."),
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
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )
    scenario_id = _normalize_required_path_id(scenario_id, label="scenario_id")

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records = svc_fetch_validation_result_executions(
            context,
            asset_id=None,
            scenario_id=scenario_id,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)
