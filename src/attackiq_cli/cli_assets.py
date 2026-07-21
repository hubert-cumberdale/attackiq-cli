from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import ASSET_FIELD_ORDER, write_csv_records, write_json
from attackiq_cli.services import (
    AssetFilters,
    ServiceContext,
    build_asset_query_params,
    build_asset_summary_records,
    build_auth_context,
    ensure_auth,
    fetch_asset_detail,
    normalize_api_backend,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_assets as svc_list_assets
from attackiq_cli.spec import SpecIndex

console = Console()

assets_app = typer.Typer(
    help="Asset commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "assets_app",
    "list_assets",
    "show_asset",
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


@assets_app.command("list")
def list_assets(
    ctx: typer.Context,
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
    page: Annotated[
        int | None,
        typer.Option("--page", help="Page number within results."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
    ] = 200,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Asset search query."),
    ] = None,
    hostname: Annotated[
        str | None,
        typer.Option("--hostname", help="Filter by asset hostname."),
    ] = None,
    ipv4_address: Annotated[
        str | None,
        typer.Option("--ipv4-address", help="Filter by IPv4 address."),
    ] = None,
    ipv6_address: Annotated[
        str | None,
        typer.Option("--ipv6-address", help="Filter by IPv6 address."),
    ] = None,
    deployment_state_id: Annotated[
        int | None,
        typer.Option("--deployment-state-id", help="Filter by deployment state number."),
    ] = None,
    deepsurface_last_seen_in_host_analysis_at: Annotated[
        str | None,
        typer.Option(
            "--deepsurface-last-seen-in-host-analysis-at",
            help="Filter by DeepSurface last host-analysis timestamp.",
        ),
    ] = None,
    deepsurface_sync_state: Annotated[
        str | None,
        typer.Option(
            "--deepsurface-sync-state",
            help="Filter by DeepSurface sync state.",
        ),
    ] = None,
    deepsurface_sync_state_changed_at: Annotated[
        str | None,
        typer.Option(
            "--deepsurface-sync-state-changed-at",
            help="Filter by DeepSurface sync-state changed timestamp.",
        ),
    ] = None,
    asset_group: Annotated[
        str | None,
        typer.Option("--asset-group", help="Filter by asset group UUID."),
    ] = None,
    activity_type: Annotated[
        str | None,
        typer.Option("--activity-type", help="Filter by DEVICE, DOMAIN, or TESTPOINT."),
    ] = None,
    ordering: Annotated[
        str | None,
        typer.Option("--ordering", help="Order by an asset field."),
    ] = None,
    api_backend: Annotated[
        str,
        typer.Option(
            "--api-backend",
            help="Experimental read-only API backend: native or platform-api.",
        ),
    ] = "native",
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
    try:
        api_backend = normalize_api_backend(api_backend)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    filters = AssetFilters(
        search=search,
        hostname=hostname,
        ipv4_address=ipv4_address,
        ipv6_address=ipv6_address,
        deployment_state_id=deployment_state_id,
        deepsurface_last_seen_in_host_analysis_at=deepsurface_last_seen_in_host_analysis_at,
        deepsurface_sync_state=deepsurface_sync_state,
        deepsurface_sync_state_changed_at=deepsurface_sync_state_changed_at,
        asset_group=asset_group,
        activity_type=activity_type,
        ordering=ordering,
    )
    try:
        query_params = build_asset_query_params(filters)
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
    op = index.get_operation("v1_assets_list")
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
        items = svc_list_assets(
            context,
            page=page,
            page_size=page_size,
            query_params=query_params or None,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
            api_backend=api_backend,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
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
    records = build_asset_summary_records(items)
    write_csv_records(output, records, preferred_fields=ASSET_FIELD_ORDER)


@assets_app.command("show")
def show_asset(
    ctx: typer.Context,
    asset_id: Annotated[
        str,
        typer.Argument(help="Asset UUID."),
    ],
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
    if insecure:
        console.print("[yellow]Warning: TLS verification disabled for this request.[/yellow]")

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_assets_retrieve")
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
        detail = fetch_asset_detail(
            context,
            asset_id=asset_id,
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
