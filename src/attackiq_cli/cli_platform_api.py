from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.mutations import write_json_payload
from attackiq_cli.services import (
    AssetFilters,
    ScenarioFilters,
    ServiceContext,
    build_asset_query_params,
    build_auth_context,
    ensure_auth,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_assets as svc_list_assets
from attackiq_cli.services import list_scenarios as svc_list_scenarios
from attackiq_cli.spec import SpecIndex

console = Console()

platform_api_app = typer.Typer(
    help="Experimental aiq-platform-api parity helpers.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "platform_api_app",
    "platform_api_parity",
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


def _write_json_to_output(output: Path | None, payload: Any) -> None:
    write_json_payload(
        output,
        payload,
        on_file_written=lambda path: console.print(f"Response written to {path}"),
    )


def _record_ids(records: list[dict[str, Any]]) -> list[str]:
    return [str(record["id"]) for record in records if record.get("id")]


def _build_backend_parity_payload(
    *,
    resource: str,
    query: dict[str, Any],
    native_records: list[dict[str, Any]],
    platform_records: list[dict[str, Any]],
) -> dict[str, Any]:
    native_ids = _record_ids(native_records)
    platform_ids = _record_ids(platform_records)
    native_id_set = set(native_ids)
    platform_id_set = set(platform_ids)
    missing_from_platform = [item for item in native_ids if item not in platform_id_set]
    extra_from_platform = [item for item in platform_ids if item not in native_id_set]
    same_order = native_ids == platform_ids
    return {
        "resource": resource,
        "query": query,
        "native": {
            "count": len(native_records),
            "ids": native_ids,
        },
        "platform_api": {
            "count": len(platform_records),
            "ids": platform_ids,
        },
        "comparison": {
            "same_ids": not missing_from_platform and not extra_from_platform,
            "same_order": same_order,
            "missing_from_platform_api": missing_from_platform,
            "extra_from_platform_api": extra_from_platform,
            "matching_ids": [item for item in native_ids if item in platform_id_set],
        },
        "parity": not missing_from_platform and not extra_from_platform and same_order,
    }


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


@platform_api_app.command("parity")
def platform_api_parity(
    ctx: typer.Context,
    resource: Annotated[
        str,
        typer.Argument(help="Read-only resource to compare: scenarios or assets."),
    ],
    search: Annotated[
        str | None,
        typer.Option("--search", help="Search query for both backends."),
    ] = None,
    page: Annotated[
        int | None,
        typer.Option("--page", help="Page number within results."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per backend page."),
    ] = 20,
    order_by: Annotated[
        str | None,
        typer.Option(
            "--order-by",
            help="Ordering field for scenarios, or asset ordering when --resource assets.",
        ),
    ] = None,
    deployment_state_id: Annotated[
        int | None,
        typer.Option(
            "--deployment-state-id",
            help="Asset deployment state filter; valid only for assets.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for parity JSON (defaults to stdout).",
        ),
    ] = None,
    fail_on_mismatch: Annotated[
        bool,
        typer.Option(
            "--fail-on-mismatch/--no-fail-on-mismatch",
            help="Exit non-zero when native and platform-api IDs differ.",
        ),
    ] = False,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    resource = resource.strip().lower()
    if resource not in {"scenarios", "assets"}:
        raise typer.BadParameter("resource must be one of: scenarios, assets.")
    if page is not None and page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if deployment_state_id is not None and resource != "assets":
        raise typer.BadParameter("--deployment-state-id is valid only for assets.")

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    auth = context.auth
    index = context.spec

    try:
        if resource == "scenarios":
            op = index.get_operation("v1_scenarios_list")
            warnings = ensure_auth(op, auth)
            for warning in warnings:
                console.print(f"[yellow]{warning}[/yellow]")
            filters = ScenarioFilters(search=search, order_by=order_by)
            native_records = svc_list_scenarios(
                context,
                page=page,
                page_size=page_size,
                filters=filters,
                insecure=insecure,
                timeout=timeout,
                api_backend="native",
            )
            platform_records = svc_list_scenarios(
                context,
                page=page,
                page_size=page_size,
                filters=filters,
                insecure=insecure,
                timeout=timeout,
                api_backend="platform-api",
            )
            query = {
                "search": search,
                "page": page,
                "page_size": page_size,
                "order_by": order_by,
            }
        else:
            op = index.get_operation("v1_assets_list")
            warnings = ensure_auth(op, auth)
            for warning in warnings:
                console.print(f"[yellow]{warning}[/yellow]")
            query_params = build_asset_query_params(
                AssetFilters(
                    search=search,
                    deployment_state_id=deployment_state_id,
                    ordering=order_by,
                )
            )
            native_records = svc_list_assets(
                context,
                page=page,
                page_size=page_size,
                query_params=query_params or None,
                insecure=insecure,
                timeout=timeout,
                api_backend="native",
            )
            platform_records = svc_list_assets(
                context,
                page=page,
                page_size=page_size,
                query_params=query_params or None,
                insecure=insecure,
                timeout=timeout,
                api_backend="platform-api",
            )
            query = {
                "search": search,
                "page": page,
                "page_size": page_size,
                "ordering": order_by,
                "deployment_state_id": deployment_state_id,
            }
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    payload = _build_backend_parity_payload(
        resource=resource,
        query=query,
        native_records=native_records,
        platform_records=platform_records,
    )
    _write_json_to_output(output, payload)
    if fail_on_mismatch and not payload["parity"]:
        raise typer.Exit(code=2)
