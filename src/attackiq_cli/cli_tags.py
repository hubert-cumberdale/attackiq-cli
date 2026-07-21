from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich import box
from rich.console import Console
from rich.table import Table

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, load_config, validate_timeout
from attackiq_cli.exporter import write_csv_records, write_json
from attackiq_cli.services import (
    ServiceContext,
    TagFilters,
    build_auth_context,
    build_tag_summary_records,
    ensure_auth,
    fetch_tag_detail,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_tags as svc_list_tags
from attackiq_cli.services import search_tags as svc_search_tags
from attackiq_cli.spec import SpecIndex

console = Console()

tags_app = typer.Typer(
    help="Tag commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "list_tags",
    "search_tags",
    "show_tag",
    "tags_app",
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


def _print_http_error_and_exit(exc: httpx.HTTPError, *, use_typer: bool = False) -> None:
    message = _format_http_error_message(exc)
    hint = None
    if isinstance(exc, httpx.ConnectError):
        hint = "Check network/DNS access and ATTACKIQ_BASE_URL."
    elif isinstance(exc, httpx.TimeoutException):
        hint = "Try increasing --timeout or check network latency."

    if use_typer:
        typer.secho(message, err=True, fg=typer.colors.RED)
        if hint:
            typer.secho(hint, err=True, fg=typer.colors.YELLOW)
    else:
        console.print(f"[red]{message}[/red]")
        if hint:
            console.print(f"[yellow]{hint}[/yellow]")
    raise typer.Exit(code=1) from exc


@tags_app.command("list")
def list_tags(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", help="Tag search query."),
    name: str | None = typer.Option(None, "--name", help="Exact tag name filter."),
    display_name: str | None = typer.Option(
        None, "--display-name", help="Exact tag display name filter."
    ),
    content_type: str | None = typer.Option(None, "--content-type", help="Content type filter."),
    exclude_tags_by_tag_set: str | None = typer.Option(
        None, "--exclude-tag-set", help="Exclude tags by tag set UUID."
    ),
    object_fingerprint: str | None = typer.Option(
        None, "--object-fingerprint", help="Object fingerprint filter."
    ),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    if exclude_tags_by_tag_set:
        try:
            uuid.UUID(exclude_tags_by_tag_set)
        except ValueError as exc:
            raise typer.BadParameter("exclude-tag-set must be a valid UUID.") from exc

    try:
        cfg = load_config()
    except ConfigError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    if warn_if_insecure_base_url(base_url):
        typer.secho(
            "Warning: Base URL uses http:// (TLS disabled).",
            err=True,
            fg=typer.colors.YELLOW,
        )
    if insecure:
        typer.secho(
            "Warning: TLS verification disabled for this request.",
            err=True,
            fg=typer.colors.YELLOW,
        )

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    tags_op = index.get_operation("v1_tags_list")
    try:
        warnings = ensure_auth(tags_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        typer.secho(warning, err=True, fg=typer.colors.YELLOW)

    filters = TagFilters(
        search=search,
        name=name,
        display_name=display_name,
        content_type=content_type,
        exclude_tags_by_tag_set=exclude_tags_by_tag_set,
        object_fingerprint=object_fingerprint,
    )

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        tags = svc_list_tags(
            context,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc, use_typer=True)

    records = build_tag_summary_records(tags)

    if fmt == "csv":
        if output is None:
            typer.secho("CSV output requires --output.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=("id", "name", "display_name"))
        return
    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)


@tags_app.command("show")
def show_tag(
    ctx: typer.Context,
    tag_id: str = typer.Argument(..., help="Tag UUID."),
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_tags_retrieve")
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
        detail = fetch_tag_detail(
            context,
            tag_id=tag_id,
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


@tags_app.command("search")
def search_tags(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search term for tags."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of tags to return."),
    output_format: str = typer.Option(
        "table",
        "--output-format",
        help="Output format: table, json, or csv.",
    ),
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for output (CSV requires --output).",
        ),
    ] = None,
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    search_term = query.strip()
    if not search_term:
        raise typer.BadParameter("query must be non-empty.")
    if limit < 1:
        raise typer.BadParameter("limit must be >= 1.")
    fmt = output_format.lower()
    if fmt not in {"table", "json", "csv"}:
        raise typer.BadParameter("output-format must be table, json, or csv.")
    if fmt == "csv" and output is None:
        typer.secho("CSV output requires --output.")
        raise typer.Exit(code=1)
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

    try:
        cfg = load_config()
    except ConfigError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    if warn_if_insecure_base_url(base_url):
        typer.secho(
            "Warning: Base URL uses http:// (TLS disabled).",
            err=True,
            fg=typer.colors.YELLOW,
        )
    if insecure:
        typer.secho(
            "Warning: TLS verification disabled for this request.",
            err=True,
            fg=typer.colors.YELLOW,
        )

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    tags_op = index.get_operation("v1_tags_list")
    try:
        warnings = ensure_auth(tags_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        typer.secho(warning, err=True, fg=typer.colors.YELLOW)

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        records = svc_search_tags(
            context,
            query=search_term,
            limit=limit,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc, use_typer=True)

    payload = build_tag_summary_records(records)

    if fmt == "csv":
        if output is None:
            typer.secho("CSV output requires --output.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, payload, preferred_fields=("id", "name", "display_name"))
        return
    if fmt == "json":
        if output is None:
            write_json(sys.stdout, payload)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, payload)
        return

    table = Table(title=f"Tags matching '{search_term}'", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Display Name")
    for tag in payload:
        table.add_row(
            str(tag.get("id") or ""),
            str(tag.get("name") or ""),
            str(tag.get("display_name") or ""),
        )
    console.print(table)
