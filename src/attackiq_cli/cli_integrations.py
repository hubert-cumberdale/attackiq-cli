from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import (
    INTEGRATION_CONNECTOR_FIELD_ORDER,
    write_csv_records,
    write_json,
)
from attackiq_cli.services import (
    IntegrationConnectorFilters,
    ServiceContext,
    build_auth_context,
    build_integration_connector_query_params,
    build_integration_connector_summary_records,
    ensure_auth,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import (
    list_integration_connectors as svc_list_integration_connectors,
)
from attackiq_cli.spec import SpecIndex

console = Console()

integrations_app = typer.Typer(
    help="Integration connector commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "integrations_app",
    "list_integrations",
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


def _parse_optional_bool(value: str | None, *, label: str) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise typer.BadParameter(f"{label} must be true or false.")


@integrations_app.command("list")
def list_integrations(
    ctx: typer.Context,
    alert_correlation_plan: Annotated[
        str | None,
        typer.Option(
            "--alert-correlation-plan",
            help="Filter by alert correlation plan UUID.",
        ),
    ] = None,
    company_connector_manager_setup: Annotated[
        str | None,
        typer.Option(
            "--company-connector-manager-setup",
            help="Filter by connector manager setup UUID.",
        ),
    ] = None,
    company_connector_manager_setup_id: Annotated[
        str | None,
        typer.Option(
            "--company-connector-manager-setup-id",
            help="Filter by connector manager setup UUID.",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Filter by connector description."),
    ] = None,
    display_name: Annotated[
        str | None,
        typer.Option("--display-name", help="Filter by connector display name."),
    ] = None,
    implemented_mixins: Annotated[
        str | None,
        typer.Option("--implemented-mixins", help="Filter by implemented mixins."),
    ] = None,
    is_deleted: Annotated[
        str | None,
        typer.Option("--is-deleted", help="Filter by deleted state: true or false."),
    ] = None,
    mode: Annotated[
        str | None,
        typer.Option("--mode", help="Filter by Ad Hoc or Automatic mode."),
    ] = None,
    mttd_timezone: Annotated[
        str | None,
        typer.Option("--mttd-timezone", help="Filter by MTTD timezone UUID."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            help=(
                "Filter by connector status (ACTIVE, DISABLED, ERROR, PENDING, TESTING, "
                "TEST_FAILED, TRANSIENT)."
            ),
        ),
    ] = None,
    ordering: Annotated[
        str | None,
        typer.Option("--ordering", help="Order by an integration connector field."),
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

    filters = IntegrationConnectorFilters(
        alert_correlation_plan=alert_correlation_plan,
        company_connector_manager_setup=company_connector_manager_setup,
        company_connector_manager_setup_id=company_connector_manager_setup_id,
        description=description,
        display_name=display_name,
        implemented_mixins=implemented_mixins,
        is_deleted=_parse_optional_bool(is_deleted, label="is-deleted"),
        mode=mode,
        mttd_timezone=mttd_timezone,
        status=status,
        ordering=ordering,
    )
    try:
        # Validate enum-like filters before loading config so local input errors fail fast.
        build_integration_connector_query_params(filters)
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
    op = index.get_operation("v1_company_connectors_list")
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
        connectors = svc_list_integration_connectors(
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

    records = build_integration_connector_summary_records(connectors)
    if fmt == "csv":
        if output is None:
            console.print("[red]CSV output requires --output.[/red]")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=INTEGRATION_CONNECTOR_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)
