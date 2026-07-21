from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import EDR_SCAN_SCHEDULE_FIELD_ORDER, write_csv_records, write_json
from attackiq_cli.services import (
    EdrScanScheduleFilters,
    ServiceContext,
    build_auth_context,
    build_edr_scan_schedule_query_params,
    build_edr_scan_schedule_summary_records,
    ensure_auth,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_edr_scan_schedules as svc_list_edr_scan_schedules
from attackiq_cli.spec import SpecIndex

console = Console()

edr_scan_schedules_app = typer.Typer(
    help="EDR scan schedule commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "edr_scan_schedules_app",
    "list_edr_scan_schedules",
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
    return f"Request failed: {exc}"


def _print_http_error_and_exit(exc: httpx.HTTPError) -> None:
    console.print(f"[red]{_format_http_error_message(exc)}[/red]")
    raise typer.Exit(code=1) from exc


def _normalize_uuid(value: str, *, label: str) -> str:
    uuid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
    )
    normalized = value.strip()
    if not uuid_pattern.match(normalized):
        raise typer.BadParameter(f"{label} must be a UUID.")
    return normalized


def _parse_optional_bool(value: str | None, *, label: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise typer.BadParameter(f"{label} must be true or false.")


@edr_scan_schedules_app.command("list")
def list_edr_scan_schedules(
    ctx: typer.Context,
    data_source: Annotated[
        str | None,
        typer.Option(
            "--data-source",
            help="Filter to schedules for a specific EDR data source UUID.",
        ),
    ] = None,
    enabled: Annotated[
        str | None,
        typer.Option("--enabled", help="Filter by enabled state: true or false."),
    ] = None,
    schedule_type: Annotated[
        str | None,
        typer.Option(
            "--schedule-type",
            help="Filter by schedule type: DAILY, ONE_SHOT, or WEEKLY.",
        ),
    ] = None,
    targeted: Annotated[
        str | None,
        typer.Option("--targeted", help="Filter by targeted state: true or false."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
    ] = 200,
    page: Annotated[
        int | None,
        typer.Option("--page", help="Page number within results."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            help="Output format: json or csv.",
        ),
    ] = "json",
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
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if page is not None and page < 1:
        raise typer.BadParameter("page must be >= 1.")
    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

    filters = EdrScanScheduleFilters(
        data_source=(
            _normalize_uuid(data_source, label="--data-source")
            if data_source is not None
            else None
        ),
        enabled=_parse_optional_bool(enabled, label="--enabled"),
        schedule_type=schedule_type,
        targeted=_parse_optional_bool(targeted, label="--targeted"),
    )
    try:
        build_edr_scan_schedule_query_params(filters)
    except ValueError as exc:
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
    op = index.get_operation("v1_emm_edr_scan_schedules_list")
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
        edr_scan_schedules = svc_list_edr_scan_schedules(
            context,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    records: list[dict[str, Any | None]] = build_edr_scan_schedule_summary_records(
        edr_scan_schedules
    )
    if fmt == "csv":
        if output is None:
            console.print("[red]CSV output requires --output.[/red]")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=EDR_SCAN_SCHEDULE_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)
