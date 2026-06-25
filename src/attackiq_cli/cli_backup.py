from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from attackiq_cli.backup import (
    BackupError,
    ConfigBackupOptions,
    normalize_backup_domains,
    run_configuration_backup,
)
from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.services import (
    ServiceContext,
    build_auth_context,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.spec import SpecIndex

console = Console()

backup_app = typer.Typer(
    help="Backup redacted tenant configuration.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "backup_app",
    "backup_configs",
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


@backup_app.command("configs")
def backup_configs(
    ctx: typer.Context,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Destination directory for redacted backup artifacts.",
        ),
    ],
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of records per API page."),
    ] = 200,
    max_pages: Annotated[
        int | None,
        typer.Option(
            "--max-pages",
            help="Maximum pages per paginated endpoint.",
        ),
    ] = None,
    company_id: Annotated[
        str | None,
        typer.Option(
            "--company-id",
            help="Company UUID to use when deriving source-type backups.",
        ),
    ] = None,
    include: Annotated[
        str | None,
        typer.Option(
            "--include",
            help=(
                "Comma-separated domains to include. Defaults to integrations,source-types,"
                "detection-rules."
            ),
        ),
    ] = None,
    endpoint_catalog: Annotated[
        Path | None,
        typer.Option(
            "--endpoint-catalog",
            exists=True,
            readable=True,
            help="Sanitized endpoint catalog JSON for reviewed discovered endpoints.",
        ),
    ] = None,
    tenant_alias: Annotated[
        str,
        typer.Option(
            "--tenant-alias",
            help="Operator-safe tenant alias to record in the manifest.",
        ),
    ] = "unspecified",
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
    if max_pages is not None and max_pages < 1:
        raise typer.BadParameter("max-pages must be >= 1.")
    if company_id is not None:
        company_id = _normalize_uuid(company_id, label="company-id")
    tenant_alias = tenant_alias.strip() or "unspecified"
    try:
        domains = normalize_backup_domains(include)
    except BackupError as exc:
        raise typer.BadParameter(str(exc)) from exc

    try:
        context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
        command_path = ctx.command_path
        if command_path.startswith("root "):
            command_path = f"attackiq {command_path.removeprefix('root ')}"
        manifest = run_configuration_backup(
            context,
            ConfigBackupOptions(
                output_dir=output_dir,
                domains=domains,
                page_size=page_size,
                max_pages=max_pages,
                company_id=company_id,
                endpoint_catalog=endpoint_catalog,
                tenant_alias=tenant_alias,
                command=command_path,
                insecure=insecure,
                timeout=timeout,
            ),
        )
    except BackupError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    console.print(f"Backup manifest written to {output_dir / 'manifest.json'}")
    console.print(f"Artifacts written: {len(manifest['artifacts'])}")
