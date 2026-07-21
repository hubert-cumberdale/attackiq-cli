from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.client import redact_headers, render_path
from attackiq_cli.config import ConfigError, load_config, validate_timeout
from attackiq_cli.exporter import SCENARIO_FIELD_ORDER, write_csv_records, write_json
from attackiq_cli.mutations import write_json_payload
from attackiq_cli.services import (
    ScenarioFilters,
    ServiceContext,
    build_auth_context,
    build_client,
    build_scenario_summary_records,
    build_scenario_template_upload_operation,
    ensure_auth,
    fetch_scenario_detail,
    normalize_api_backend,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_scenarios as svc_list_scenarios
from attackiq_cli.spec import SpecIndex

console = Console()

scenarios_app = typer.Typer(
    help="Scenario commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "ScenarioFilters",
    "list_scenarios",
    "scenarios_app",
    "show_scenario",
    "upload_scenario_packages",
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


def _write_json_to_output(output: Path | None, payload: Any) -> None:
    write_json_payload(
        output,
        payload,
        on_file_written=lambda path: console.print(f"Response written to {path}"),
    )


@scenarios_app.command("list")
def list_scenarios(
    ctx: typer.Context,
    output_format: Annotated[
        str,
        typer.Option("--output-format", help="Output format: json or csv."),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for output (defaults to stdout).",
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
    order_by: Annotated[
        str | None,
        typer.Option("--order-by", help="Order by a specific field."),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Scenario search query."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", help="Scenario tag name or ID filter."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Exact scenario name to match."),
    ] = None,
    modified_after: Annotated[
        str | None,
        typer.Option(
            "--modified-after",
            help="Filter scenarios modified at or after this date-time (ISO 8601).",
        ),
    ] = None,
    last_updated: Annotated[
        str | None,
        typer.Option("--last-updated", help="Deprecated alias for --modified-after."),
    ] = None,
    mitre_platforms: Annotated[
        str | None,
        typer.Option("--mitre-platforms", help="Filter by MITRE platforms (API format)."),
    ] = None,
    hierarchy: Annotated[
        str | None,
        typer.Option("--hierarchy", help="Hierarchy filter."),
    ] = None,
    object_fingerprint: Annotated[
        str | None,
        typer.Option("--object-fingerprint", help="Scenario object fingerprint."),
    ] = None,
    parameters_description: Annotated[
        str | None,
        typer.Option("--parameters-description", help="Filter by parameters description."),
    ] = None,
    scenario_template_instance: Annotated[
        str | None,
        typer.Option(
            "--scenario-template-instance",
            help="Scenario template instance UUID filter.",
        ),
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
    if page is not None and page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    try:
        api_backend = normalize_api_backend(api_backend)
    except ValueError as exc:
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
    scenarios_op = index.get_operation("v1_scenarios_list")
    try:
        warnings = ensure_auth(scenarios_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        typer.secho(warning, err=True, fg=typer.colors.YELLOW)

    filters = ScenarioFilters(
        order_by=order_by,
        search=search,
        tag=tag,
        name=name,
        modified_after=modified_after,
        last_updated=last_updated,
        mitre_platforms=mitre_platforms,
        hierarchy=hierarchy,
        object_fingerprint=object_fingerprint,
        parameters_description=parameters_description,
        scenario_template_instance=scenario_template_instance,
    )

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        scenarios = svc_list_scenarios(
            context,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
            api_backend=api_backend,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc, use_typer=True)

    if fmt == "csv":
        if output is None:
            typer.secho("CSV output requires --output.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        records = build_scenario_summary_records(scenarios)
        write_csv_records(output, records, preferred_fields=SCENARIO_FIELD_ORDER)
        return
    if output is None:
        write_json(sys.stdout, scenarios)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, scenarios)


@scenarios_app.command("show")
def show_scenario(
    ctx: typer.Context,
    scenario_id: Annotated[str, typer.Argument(help="Scenario ID (UUID).")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for output (defaults to stdout for JSON).",
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
    scenario_op = index.get_operation("v1_scenarios_retrieve")
    try:
        warnings = ensure_auth(scenario_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        typer.secho(warning, err=True, fg=typer.colors.YELLOW)

    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        scenario = fetch_scenario_detail(
            context,
            scenario_id=scenario_id,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc, use_typer=True)

    if output is None:
        write_json(sys.stdout, scenario)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, scenario)


def _validate_upload_endpoint(endpoint: str) -> str:
    cleaned = (endpoint or "").strip()
    if not cleaned:
        raise typer.BadParameter("endpoint cannot be empty.")
    if "://" in cleaned:
        raise typer.BadParameter("endpoint must be a relative API path, not a full URL.")
    if "?" in cleaned or "#" in cleaned:
        raise typer.BadParameter("endpoint must not include query strings or fragments.")
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned.rstrip("/") or "/"


def _validate_upload_field_name(field_name: str) -> str:
    cleaned = (field_name or "").strip()
    if not cleaned:
        raise typer.BadParameter("field-name cannot be empty.")
    if any(char.isspace() for char in cleaned):
        raise typer.BadParameter("field-name must not contain whitespace.")
    return cleaned


def _validate_scenario_package(path: Path) -> Path:
    package = path.expanduser()
    if not package.exists():
        raise typer.BadParameter(f"Scenario package not found: {package}")
    if not package.is_file():
        raise typer.BadParameter(f"Scenario package must be a file: {package}")
    if package.suffix.lower() != ".zip":
        raise typer.BadParameter("Scenario package must be a .zip file.")
    return package


def _response_payload(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return response.text
    try:
        return response.json()
    except json.JSONDecodeError:
        return response.text


_UPLOAD_REDACTION = "***"
_UPLOAD_SECRET_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "jwt",
    "password",
    "secret",
    "signature",
    "token",
)
_UPLOAD_URL_KEY_PARTS = (
    "download_url",
    "package_url",
    "signed_url",
    "static_url",
    "upload_url",
    "url",
)
_UPLOAD_SECRET_TEXT_RE = re.compile(
    r"(?i)(authorization|api[_-]?key|jwt|password|secret|signature|token)\s*[:=]"
)


def _is_upload_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _UPLOAD_SECRET_KEY_PARTS + _UPLOAD_URL_KEY_PARTS)


def _is_upload_sensitive_string(value: str) -> bool:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered.startswith(("http://", "https://")):
        return True
    return bool(_UPLOAD_SECRET_TEXT_RE.search(stripped))


def _redact_upload_response_payload(payload: Any, *, sensitive_context: bool = False) -> Any:
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            sensitive_key = _is_upload_sensitive_key(str(key))
            redacted[key] = _redact_upload_response_payload(
                value,
                sensitive_context=sensitive_context or sensitive_key,
            )
        return redacted
    if isinstance(payload, list):
        return [
            _redact_upload_response_payload(item, sensitive_context=sensitive_context)
            for item in payload
        ]
    if isinstance(payload, str):
        if sensitive_context or _is_upload_sensitive_string(payload):
            return _UPLOAD_REDACTION
        return payload
    return _UPLOAD_REDACTION if sensitive_context and payload is not None else payload


@scenarios_app.command("upload")
def upload_scenario_packages(
    packages: Annotated[
        list[Path],
        typer.Argument(help="Scenario Wizard package zip(s) to upload."),
    ],
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Perform the upload. Without --apply, print a dry-run request plan.",
        ),
    ] = False,
    endpoint: Annotated[
        str,
        typer.Option(
            "--endpoint",
            help="Relative out-of-spec upload endpoint captured from the UI.",
        ),
    ] = "/v1/scenario_templates",
    field_name: Annotated[
        str,
        typer.Option("--field-name", help="Multipart form field name for the scenario package."),
    ] = "zip_file",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON dry-run or upload responses.",
        ),
    ] = None,
    raw_response: Annotated[
        bool,
        typer.Option(
            "--raw-response",
            help="Include unredacted upload response bodies. Use only for trusted local output.",
        ),
    ] = False,
    auth_scheme: Annotated[
        str,
        typer.Option(
            "--auth-scheme",
            help="auto | account-token | jwt | none (override auth resolution).",
        ),
    ] = "auto",
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    """Upload custom Scenario Wizard packages through the captured UI endpoint."""
    if not packages:
        raise typer.BadParameter("At least one scenario package is required.")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    scheme_normalized = auth_scheme.lower()
    if scheme_normalized not in {"auto", "account-token", "jwt", "none"}:
        raise typer.BadParameter("auth-scheme must be one of: auto, account-token, jwt, none.")

    endpoint = _validate_upload_endpoint(endpoint)
    field_name = _validate_upload_field_name(field_name)
    package_paths = [_validate_scenario_package(path) for path in packages]

    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)
    if insecure:
        console.print("[yellow]Warning: TLS verification disabled for this request.[/yellow]")

    auth = build_auth_context(cfg, preferred_scheme=scheme_normalized)
    op = build_scenario_template_upload_operation()
    op.path = endpoint
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    if not apply:
        preview = {
            "operation_id": op.operation_id,
            "method": op.method.upper(),
            "url": f"{base_url}{render_path(op.path, {})}",
            "headers": redact_headers(auth.build_headers(op)),
            "multipart_file_field": field_name,
            "packages": [
                {
                    "path": str(path),
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                }
                for path in package_paths
            ],
        }
        _write_json_to_output(output, preview)
        return

    results: list[dict[str, Any]] = []
    try:
        with build_client(base_url, cfg, auth, insecure=insecure, timeout=timeout) as client:
            for path in package_paths:
                with path.open("rb") as handle:
                    response = client.send(
                        op,
                        path_params={},
                        query_params={},
                        headers={},
                        files=[(field_name, (path.name, handle, "application/zip"))],
                    )
                response_payload = _response_payload(response)
                if not raw_response:
                    response_payload = _redact_upload_response_payload(response_payload)
                results.append(
                    {
                        "package": str(path),
                        "filename": path.name,
                        "status_code": response.status_code,
                        "response": response_payload,
                    }
                )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_json_to_output(output, results)
