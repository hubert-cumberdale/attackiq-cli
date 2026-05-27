from __future__ import annotations

from typing import Any

import typer

from attackiq_cli.client import AttackIQClient, AuthContext
from attackiq_cli.config import load_config
from attackiq_cli.logging_utils import setup_logging
from attackiq_cli.spec import Operation, load_spec

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("list-items")
def list_items(
    ctx: typer.Context,
    page_size: int = typer.Option(200, "--page-size", help="Page size for pagination."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    """Template command for a paginated GET endpoint."""
    config = load_config()
    base_url = config.base_url
    if not base_url:
        raise typer.BadParameter("Base URL is not set. Use --base-url or `attackiq config set`.")

    logger = setup_logging(config.log_level, config.log_json)
    auth = AuthContext(config.account_token, config.jwt, preferred_scheme=config.auth_scheme)
    spec = load_spec(config.spec_path)
    operation: Operation = spec.require_operation("listItems")

    with AttackIQClient(
        base_url,
        auth,
        verify_tls=not insecure,
        timeout=timeout or config.timeout,
        logger=logger,
    ) as client:
        payload = client.send(
            operation,
            path_params={},
            query_params={"page_size": page_size},
            headers={},
        ).json()

    items: list[dict[str, Any]] = payload.get("results", [])
    typer.echo(typer.style(f"Fetched {len(items)} items", fg=typer.colors.GREEN))


# To register: import this module and add to the root Typer app.
# Example: app.add_typer(list_items.app, name="items")
