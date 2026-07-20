from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from attackiq_cli.config import (
    LOG_LEVELS,
    CliConfig,
    ConfigError,
    load_config,
    normalize_base_url,
    save_config,
    validate_effective_config,
    validate_timeout,
)
from attackiq_cli.services import warn_if_insecure_base_url

console = Console()

config_app = typer.Typer(
    help="Configure defaults (base URL, timeouts, TLS).",
    pretty_exceptions_show_locals=False,
)
auth_app = typer.Typer(
    help="Manage authentication tokens.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "auth_app",
    "clear_auth",
    "config_app",
    "load_config_or_exit",
    "mask_secret",
    "set_auth",
    "set_config",
    "show_config",
    "validate_config",
    "warn_if_insecure",
]


def load_config_or_exit() -> CliConfig:
    try:
        return load_config()
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def warn_if_insecure(base_url: str) -> None:
    if warn_if_insecure_base_url(base_url):
        console.print("[yellow]Warning: Base URL uses http:// (TLS disabled).[/yellow]")


@config_app.command("show")
def show_config() -> None:
    cfg = load_config_or_exit()
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Base URL", cfg.base_url or "")
    table.add_row("Verify TLS", str(cfg.verify_tls))
    table.add_row("Timeout (s)", str(cfg.timeout))
    table.add_row("Log JSON", str(cfg.log_json))
    table.add_row("Log Level", cfg.log_level)
    table.add_row("Account Token", mask_secret(cfg.account_token))
    table.add_row("JWT", mask_secret(cfg.jwt))
    console.print(table)


@config_app.command(
    "validate",
    help="Validate effective config and warn on risky settings. Example: attackiq config validate",
)
def validate_config() -> None:
    cfg = load_config_or_exit()
    errors, warnings = validate_effective_config(cfg)
    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"- {warning}")
    if errors:
        console.print("[red]Errors:[/red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)
    console.print("[green]Config OK[/green]")


@config_app.command("set")
def set_config(
    base_url: str | None = typer.Option(None, help="Default API base URL."),
    verify_tls_on: bool = typer.Option(False, "--verify-tls", help="Enable TLS verification."),
    verify_tls_off: bool = typer.Option(False, "--no-verify-tls", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, help="Request timeout in seconds."),
    log_json: bool | None = typer.Option(
        None, "--log-json/--no-log-json", help="Enable JSON structured logging."
    ),
    log_level: str | None = typer.Option(
        None,
        help=f"Logging level ({', '.join(sorted(LOG_LEVELS))}).",
    ),
) -> None:
    cfg = load_config_or_exit()
    if base_url:
        try:
            cfg.base_url = normalize_base_url(base_url)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
        warn_if_insecure(cfg.base_url)
    if verify_tls_on and verify_tls_off:
        raise typer.BadParameter("Use only one of --verify-tls or --no-verify-tls.")
    if verify_tls_on:
        cfg.verify_tls = True
    if verify_tls_off:
        cfg.verify_tls = False
    if timeout is not None:
        try:
            cfg.timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    if log_json is not None:
        cfg.log_json = log_json
    if log_level is not None:
        if log_level.strip().upper() not in LOG_LEVELS:
            raise typer.BadParameter(f"log-level must be one of: {', '.join(sorted(LOG_LEVELS))}.")
        cfg.log_level = log_level.strip().upper()
    path = save_config(cfg)
    console.print(f"Config saved to {path}")


@auth_app.command("set")
def set_auth(
    account_token: str | None = typer.Option(None, help="Account Token (stored locally)."),
    jwt: str | None = typer.Option(None, help="JSON Web Token (stored locally)."),
) -> None:
    if not account_token and not jwt:
        raise typer.BadParameter("Provide --account-token and/or --jwt.")
    cfg = load_config_or_exit()
    if account_token:
        cfg.account_token = account_token.strip()
    if jwt:
        cfg.jwt = jwt.strip()
    path = save_config(cfg)
    console.print(f"Credentials stored at {path}")


@auth_app.command("clear")
def clear_auth() -> None:
    cfg = load_config_or_exit()
    cfg.account_token = None
    cfg.jwt = None
    save_config(cfg)
    console.print("Credentials cleared from config. Environment variables remain unchanged.")


def mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if len(secret) <= 4:
        return "***"
    return f"{secret[:2]}***{secret[-2:]}"
