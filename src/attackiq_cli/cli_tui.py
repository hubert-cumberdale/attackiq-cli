from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from attackiq_cli.config import ConfigError, validate_timeout

console = Console()

__all__ = ["tui"]


def tui(
    ctx: typer.Context,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Scenarios page size."),
    ] = 20,
    order_by: Annotated[
        str | None,
        typer.Option("--order-by", help="Scenario order_by value (per API support)."),
    ] = "last_updated",
    search: Annotated[
        str | None,
        typer.Option("--search", help="Scenario search query."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", help="Scenario tag name or ID filter."),
    ] = None,
    filter_debounce: Annotated[
        float,
        typer.Option("--filter-debounce", help="Filter debounce in seconds (min 0.1)."),
    ] = 0.4,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
    auth_scheme: Annotated[
        str,
        typer.Option(help="auto | account-token | jwt | none (override auth resolution)."),
    ] = "auto",
    insecure: Annotated[
        bool,
        typer.Option(
            "--insecure",
            help="Disable TLS verification (avoid unless necessary).",
        ),
    ] = False,
) -> None:
    scheme_normalized = auth_scheme.lower()
    if scheme_normalized not in {"auto", "account-token", "jwt", "none"}:
        raise typer.BadParameter("auth-scheme must be one of: auto, account-token, jwt, none.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    if filter_debounce < 0.1:
        raise typer.BadParameter("filter-debounce must be >= 0.1.")
    if insecure:
        console.print("[yellow]Warning: TLS verification disabled for this session.[/yellow]")
    if order_by and not order_by.strip():
        order_by = None
    if search and not search.strip():
        search = None
    if tag and not tag.strip():
        tag = None
    from attackiq_cli.tui import run_tui

    run_tui(
        spec_path=ctx.obj["spec_path"],
        page_size=page_size,
        order_by=order_by,
        search=search,
        tag=tag,
        filter_debounce=filter_debounce,
        insecure=insecure,
        timeout=timeout,
        auth_scheme=scheme_normalized,
    )
