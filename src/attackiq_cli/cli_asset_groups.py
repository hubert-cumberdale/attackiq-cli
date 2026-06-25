from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import ASSET_GROUP_FIELD_ORDER, write_csv_records, write_json
from attackiq_cli.services import (
    AssetGroupFilters,
    ServiceContext,
    build_asset_group_summary_records,
    build_auth_context,
    ensure_auth,
    fetch_asset_group_detail,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_asset_groups as svc_list_asset_groups
from attackiq_cli.spec import SpecIndex

console = Console()

asset_groups_app = typer.Typer(
    help="Asset group commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "asset_groups_app",
    "list_asset_groups",
    "show_asset_group",
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


@asset_groups_app.command("list")
def list_asset_groups(
    ctx: typer.Context,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Asset group search query."),
    ] = None,
    asset_group_id: Annotated[
        str | None,
        typer.Option(
            "--id",
            "--asset-group-id",
            help="Filter by asset group UUID.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Exact asset group name filter."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Asset group description filter."),
    ] = None,
    company: Annotated[
        str | None,
        typer.Option("--company", help="Filter by company UUID."),
    ] = None,
    company_id: Annotated[
        str | None,
        typer.Option("--company-id", help="Filter by company UUID."),
    ] = None,
    user: Annotated[
        str | None,
        typer.Option("--user", help="Filter by user UUID."),
    ] = None,
    user_id: Annotated[
        str | None,
        typer.Option("--user-id", help="Filter by user UUID."),
    ] = None,
    created: Annotated[
        str | None,
        typer.Option("--created", help="Filter by created timestamp."),
    ] = None,
    created_after: Annotated[
        str | None,
        typer.Option("--created-after", help="Filter by created-after timestamp."),
    ] = None,
    modified: Annotated[
        str | None,
        typer.Option("--modified", help="Filter by modified timestamp."),
    ] = None,
    ordering: Annotated[
        str | None,
        typer.Option("--ordering", help="Order by an asset group field."),
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
    op = index.get_operation("v1_asset_groups_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    filters = AssetGroupFilters(
        search=search,
        asset_group_id=asset_group_id,
        name=name,
        description=description,
        company=company,
        company_id=company_id,
        user=user,
        user_id=user_id,
        created=created,
        created_after=created_after,
        modified=modified,
        ordering=ordering,
    )
    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        asset_groups = svc_list_asset_groups(
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

    if fmt == "csv":
        if output is None:
            console.print("[red]CSV output requires --output.[/red]")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        records = build_asset_group_summary_records(asset_groups)
        write_csv_records(output, records, preferred_fields=ASSET_GROUP_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, asset_groups)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, asset_groups)


@asset_groups_app.command("show")
def show_asset_group(
    ctx: typer.Context,
    asset_group_id: Annotated[
        str,
        typer.Argument(help="Asset group UUID."),
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
    op = index.get_operation("v1_asset_groups_retrieve")
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
        detail = fetch_asset_group_detail(
            context,
            asset_group_id=asset_group_id,
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
