from __future__ import annotations

import contextlib
import csv
import json
import sys
from pathlib import Path
from typing import Annotated, Any, TextIO

import httpx
import typer
from rich.console import Console
from rich.panel import Panel

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.client import redact_headers, render_path
from attackiq_cli.config import LOG_LEVELS, ConfigError, validate_timeout
from attackiq_cli.exporter import fieldnames_for_records, normalize_csv_value, write_csv_records
from attackiq_cli.logging_utils import setup_logging
from attackiq_cli.services import (
    build_auth_context,
    build_client,
    ensure_auth,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.spec import Operation, SpecIndex
from attackiq_cli.utils import (
    coerce_value_from_schema,
    load_json_payload,
    parse_key_value_pairs,
    validate_json_payload,
)

console = Console()

__all__ = [
    "call",
    "coerce_params",
    "handle_response",
    "parse_cookie_header",
    "parse_form_files",
    "prompt_for_body",
    "prompt_for_missing_required",
    "segregate_params",
    "validate_header_values",
]


def warn_if_insecure(base_url: str) -> None:
    if warn_if_insecure_base_url(base_url):
        console.print("[yellow]Warning: Base URL uses http:// (TLS disabled).[/yellow]")


def prompt_for_missing_required(
    index: SpecIndex,
    operation: Operation,
    params: dict[str, Any],
    headers: dict[str, str],
    cookies: dict[str, str],
) -> None:
    for name in sorted(index.required_parameters(operation, "path")):
        if name not in params:
            params[name] = typer.prompt(f"Enter path parameter '{name}'")
    for name in sorted(index.required_parameters(operation, "query")):
        if name not in params:
            params[name] = typer.prompt(f"Enter query parameter '{name}'")
    header_names = {key.lower() for key in headers}
    for name in sorted(index.required_parameters(operation, "header")):
        if name.lower() not in header_names:
            headers[name] = typer.prompt(f"Enter header '{name}'")
            header_names.add(name.lower())
    cookie_header_key = next((key for key in headers if key.lower() == "cookie"), None)
    cookie_header_values = (
        parse_cookie_header(headers[cookie_header_key])
        if cookie_header_key and headers[cookie_header_key]
        else {}
    )
    for name in sorted(index.required_parameters(operation, "cookie")):
        if name not in cookies and name not in cookie_header_values:
            cookies[name] = typer.prompt(f"Enter cookie '{name}'")


def prompt_for_body(
    index: SpecIndex,
    operation: Operation,
) -> tuple[dict[str, str], list[str], Any]:
    content_types = index.request_body_content_types(operation)
    allowed = []
    if not content_types or "application/json" in content_types:
        allowed.append("json")
    if "application/x-www-form-urlencoded" in content_types:
        allowed.append("form")
    if "multipart/form-data" in content_types:
        allowed.append("form-file")
    if not allowed:
        allowed = ["json"]

    choice = typer.prompt(
        "Request body type (json/form/form-file)",
        default=allowed[0],
        show_default=True,
    ).strip().lower()
    if choice not in allowed:
        raise typer.BadParameter(
            f"Request body type must be one of: {', '.join(sorted(allowed))}."
        )
    if choice == "json":
        for _ in range(3):
            raw = typer.prompt("Enter JSON body")
            try:
                return {}, [], json.loads(raw)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON. Try again.[/red]")
        raise typer.BadParameter("Invalid JSON body.")
    form_fields: dict[str, str] = {}
    form_files: list[str] = []
    raw_fields = typer.prompt(
        "Form fields (key=value, comma separated)",
        default="",
        show_default=False,
    ).strip()
    if raw_fields:
        form_fields = parse_key_value_pairs(
            [item.strip() for item in raw_fields.split(",") if item.strip()],
            coerce=False,
        )
    if choice == "form-file":
        raw_files = typer.prompt(
            "Form files (key=path, comma separated)",
            default="",
            show_default=False,
        ).strip()
        if not raw_files:
            raise typer.BadParameter("Form files are required for form-file mode.")
        form_files = [item.strip() for item in raw_files.split(",") if item.strip()]
    return form_fields, form_files, None


def parse_form_files(
    items: list[str],
) -> tuple[list[tuple[str, tuple[str, Any, str | None]]], list[Any]]:
    files: list[tuple[str, tuple[str, Any, str | None]]] = []
    handles: list[Any] = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected key=path pair, got '{item}'")
        key, value = item.split("=", 1)
        key = key.strip()
        path_value = value.strip()
        if not key:
            raise ValueError("Form file keys cannot be empty.")
        if not path_value:
            raise ValueError("Form file paths cannot be empty.")
        file_path = Path(path_value)
        if not file_path.exists():
            raise ValueError(f"Form file not found: {file_path}")
        handle = file_path.open("rb")
        handles.append(handle)
        files.append((key, (file_path.name, handle, None)))
    return files, handles


def call(
    ctx: typer.Context,
    operation_id: Annotated[
        str,
        typer.Argument(help="operationId from the OpenAPI schema."),
    ],
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-p", help="key=value pairs for path/query parameters."),
    ] = None,
    header: Annotated[
        list[str] | None,
        typer.Option("--header", "-H", help="Custom headers (key=value)."),
    ] = None,
    cookie: Annotated[
        list[str] | None,
        typer.Option("--cookie", help="Cookie parameters (key=value)."),
    ] = None,
    body: Annotated[
        str | None,
        typer.Option(help="JSON body string."),
    ] = None,
    body_file: Annotated[
        Path | None,
        typer.Option(exists=True, readable=True, help="Load JSON body from a file."),
    ] = None,
    form: Annotated[
        list[str] | None,
        typer.Option("--form", help="Form fields (key=value)."),
    ] = None,
    form_file: Annotated[
        list[str] | None,
        typer.Option("--form-file", help="Form files (key=path)."),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Prompt for missing parameters or request bodies.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(help="Write response body to a file."),
    ] = None,
    output_format: Annotated[
        str | None,
        typer.Option("--output-format", help="Response format: pretty-json | raw | csv."),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(help="Override base URL for this call."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option(help="Override request timeout."),
    ] = None,
    log_json: Annotated[
        bool | None,
        typer.Option("--log-json/--no-log-json", help="Enable JSON structured logging."),
    ] = None,
    log_level: Annotated[
        str | None,
        typer.Option(help=f"Logging level ({', '.join(sorted(LOG_LEVELS))})."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging."),
    ] = False,
    auth_scheme: Annotated[
        str,
        typer.Option(help="auto | account-token | jwt | none (override auth resolution)."),
    ] = "auto",
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification (avoid unless necessary)."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show the request without sending it."),
    ] = False,
) -> None:
    cfg = load_config_or_exit()
    log_json_effective = cfg.log_json if log_json is None else log_json
    if log_level is None and verbose:
        log_level_effective = "DEBUG"
    else:
        log_level_effective = cfg.log_level if log_level is None else log_level.strip().upper()
    if log_level_effective not in LOG_LEVELS:
        raise typer.BadParameter(f"log-level must be one of: {', '.join(sorted(LOG_LEVELS))}.")
    logger = setup_logging(log_level_effective, log_json_effective)
    spec_path: Path = ctx.obj["spec_path"]
    index = SpecIndex.from_file(spec_path)
    op = index.get_operation(operation_id)

    try:
        form_handles: list[Any] = []
        if (body or body_file) and (form or form_file):
            raise ValueError("Use either JSON body options or form options, not both.")
        params = parse_key_value_pairs(param or [], coerce=False)
        headers = parse_key_value_pairs(header or [], coerce=False)
        cookies = parse_key_value_pairs(cookie or [], coerce=False)
        body_payload = load_json_payload(body, body_file)
        form_fields = parse_key_value_pairs(form or [], coerce=False) if form else {}
        form_files, form_handles = parse_form_files(form_file or []) if form_file else ([], [])
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if interactive:
        prompt_for_missing_required(index, op, params, headers, cookies)
        if not body_payload and not form_fields and not form_files and op.request_body:
            try:
                prompted_fields, prompted_files, prompted_body = prompt_for_body(index, op)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
            form_fields = prompted_fields or form_fields
            if prompted_files:
                form_files, additional_handles = parse_form_files(prompted_files)
                form_handles.extend(additional_handles)
            body_payload = prompted_body if prompted_body is not None else body_payload
    path_params, query_params = segregate_params(index, op, params)
    try:
        path_params = coerce_params(index, op, path_params, "path")
        query_params = coerce_params(index, op, query_params, "query")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    missing_path = [p for p in index.required_parameters(op, "path") if p not in path_params]
    if missing_path:
        raise typer.BadParameter(f"Missing required path parameters: {', '.join(missing_path)}")

    cookie_header_key = next((key for key in headers if key.lower() == "cookie"), None)
    cookie_header_values = (
        parse_cookie_header(headers[cookie_header_key])
        if cookie_header_key and headers[cookie_header_key]
        else {}
    )
    combined_cookies = {**cookie_header_values, **cookies}
    try:
        headers = coerce_params(index, op, headers, "header")
        combined_cookies = coerce_params(index, op, combined_cookies, "cookie")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    headers = {key: str(value) for key, value in headers.items()}

    missing_messages = []
    required_headers = index.required_parameters(op, "header")
    if required_headers:
        header_names = {name.lower() for name in headers}
        missing_headers = [
            name for name in required_headers if name.lower() not in header_names
        ]
        if missing_headers:
            missing_messages.append(
                f"Missing required header parameters: {', '.join(missing_headers)}"
            )

    required_cookies = index.required_parameters(op, "cookie")
    if required_cookies:
        missing_cookies = [name for name in required_cookies if name not in combined_cookies]
        if missing_cookies:
            missing_messages.append(
                f"Missing required cookie parameters: {', '.join(missing_cookies)}"
            )

    if missing_messages:
        raise typer.BadParameter("\n".join(missing_messages))

    has_request_body = bool(body_payload is not None or form_fields or form_files)
    if op.request_body and not has_request_body and op.request_body.get("required"):
        raise typer.BadParameter("Request body is required by this operation.")
    if body_payload is not None:
        skip_tags = {"mssp_public", "aev", "public", "detection engineering"}
        op_tags = {tag.lower() for tag in op.tags}
        if not (skip_tags & op_tags):
            body_schema = index.request_body_schema(op)
            if body_schema:
                errors = validate_json_payload(body_payload, body_schema, index.resolve_schema)
                if errors:
                    joined = "\n".join(f"- {error}" for error in errors)
                    raise typer.BadParameter(f"Body validation failed:\n{joined}")
    content_types = index.request_body_content_types(op)
    if form_fields or form_files:
        expected = "multipart/form-data" if form_files else "application/x-www-form-urlencoded"
        allowed = {"multipart/form-data", "application/x-www-form-urlencoded"}
        if content_types and not (set(content_types) & allowed):
            console.print(
                f"[yellow]Warning: Spec does not list {expected} for this operation.[/yellow]"
            )
    if body_payload is not None and content_types and "application/json" not in content_types:
        console.print(
            "[yellow]Warning: Spec does not list application/json for this operation.[/yellow]"
        )
    try:
        resolved_base_url = resolve_base_url(cfg, base_url)
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    warn_if_insecure(resolved_base_url)

    scheme_normalized = auth_scheme.lower()
    if scheme_normalized not in {"auto", "account-token", "jwt", "none"}:
        raise typer.BadParameter("auth-scheme must be one of: auto, account-token, jwt, none.")

    auth = build_auth_context(cfg, preferred_scheme=scheme_normalized)
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")
    if insecure:
        console.print("[yellow]Warning: TLS verification disabled for this request.[/yellow]")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    if cookies:
        cookie_value = "; ".join(
            f"{key}={value}" for key, value in combined_cookies.items()
        )
        if cookie_header_key:
            headers[cookie_header_key] = cookie_value
        else:
            headers["Cookie"] = cookie_value

    if output_format is not None:
        output_format = output_format.strip().lower()
        if output_format not in {"pretty-json", "raw", "csv"}:
            raise typer.BadParameter("output-format must be one of: pretty-json, raw, csv.")

    validate_header_values(headers)

    if dry_run:
        preview_headers = redact_headers(headers)
        preview_headers.update(redact_headers(auth.build_headers(op)))
        preview_files = [f"{field}={filename}" for field, (filename, _handle, _ctype) in form_files]
        preview = {
            "url": f"{resolved_base_url}{render_path(op.path, path_params)}",
            "method": op.method.upper(),
            "path_params": path_params,
            "query_params": query_params,
            "headers": preview_headers,
            "body": body_payload,
            "form_fields": form_fields,
            "form_files": preview_files,
        }
        console.print(Panel(json.dumps(preview, indent=2), title="Dry Run"))
        return

    try:
        with build_client(
            resolved_base_url,
            cfg,
            auth,
            insecure=insecure,
            timeout=timeout,
            logger=logger,
        ) as client:
            response = client.send(
                op,
                path_params=path_params,
                query_params=query_params,
                headers=headers,
                json_body=body_payload,
                data_body=form_fields or None,
                files=form_files or None,
            )
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Request failed ({exc.response.status_code}):[/red] {exc}")
        try:
            console.print(exc.response.json())
        except Exception:
            console.print(exc.response.text)
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # pragma: no cover - defensive
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        for handle in form_handles:
            with contextlib.suppress(Exception):
                handle.close()

    handle_response(response, output, output_format)


def handle_response(
    response: httpx.Response, output: Path | None, output_format: str | None
) -> None:
    content_type = response.headers.get("content-type", "")
    is_json = "application/json" in content_type

    if output_format is None:
        payload: str
        if is_json:
            try:
                payload = json.dumps(response.json(), indent=2)
            except json.JSONDecodeError:
                payload = response.text
        else:
            payload = response.text
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
            console.print(f"Response written to {output}")
        return

    def write_text_payload(value: str, add_newline: bool) -> None:
        if add_newline and not value.endswith("\n"):
            value = f"{value}\n"
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(value, encoding="utf-8")
            console.print(f"Response written to {output}")
            return
        sys.stdout.write(value)

    def write_csv_payload(records: list[dict[str, Any]]) -> None:
        if output is None:
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records)
        console.print(f"Response written to {output}")

    def write_csv_stream(handle: TextIO, records: list[dict[str, Any]]) -> None:
        fieldnames = fieldnames_for_records(records)
        writer = csv.writer(handle)
        if fieldnames:
            writer.writerow(fieldnames)
        for record in records:
            writer.writerow(
                [normalize_csv_value(record.get(field)) for field in fieldnames]
            )

    if output_format == "raw":
        write_text_payload(response.text, add_newline=False)
        return

    if output_format == "pretty-json":
        if is_json:
            try:
                payload = json.dumps(response.json(), indent=2)
            except json.JSONDecodeError:
                payload = response.text
            write_text_payload(payload, add_newline=True)
            return
        write_text_payload(response.text, add_newline=False)
        return

    if not is_json:
        console.print("[red]CSV output requires a JSON response.[/red]")
        raise typer.Exit(code=1)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        console.print(f"[red]CSV output requires valid JSON: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        console.print("[red]CSV output requires a JSON array of objects.[/red]")
        raise typer.Exit(code=1)
    if output:
        write_csv_payload(payload)
    else:
        write_csv_stream(sys.stdout, payload)


def segregate_params(index: SpecIndex, op: Operation, params: dict) -> tuple[dict, dict]:
    path_names = set(index.parameter_names(op, "path"))
    query_names = set(index.parameter_names(op, "query"))
    header_names = set(index.parameter_names(op, "header"))
    cookie_names = set(index.parameter_names(op, "cookie"))
    path_params = {}
    query_params = {}
    for key, value in params.items():
        if key in path_names:
            path_params[key] = value
        elif key in header_names:
            raise typer.BadParameter(
                f"Parameter '{key}' is defined as a header; use --header."
            )
        elif key in cookie_names:
            raise typer.BadParameter(
                f"Parameter '{key}' is defined as a cookie; use --cookie."
            )
        elif not query_names or key in query_names:
            query_params[key] = value
        else:
            raise typer.BadParameter(f"Parameter '{key}' is not defined for this operation.")
    return path_params, query_params


def coerce_params(
    index: SpecIndex, op: Operation, params: dict[str, Any], location: str
) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for key, value in params.items():
        schema = index.parameter_schema(op, location, key)
        if schema is None and location == "header":
            schema = _resolve_header_schema(index, op, key)
        if schema is None:
            coerced[key] = value
            continue
        try:
            coerced[key] = coerce_value_from_schema(str(value), schema)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid value for {location} parameter '{key}': {exc}") from exc
    return coerced


def _resolve_header_schema(
    index: SpecIndex, op: Operation, name: str
) -> dict[str, Any] | None:
    target = name.lower()
    for param in op.parameters:
        if param.get("in") != "header":
            continue
        param_name = str(param.get("name", ""))
        if param_name.lower() != target:
            continue
        schema = param.get("schema") or {}
        if isinstance(schema, dict):
            return index.resolve_schema(schema)
        return {}
    return None


def parse_cookie_header(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in value.split(";"):
        if "=" not in part:
            continue
        name, raw_value = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        parsed[name] = raw_value.strip()
    return parsed


def validate_header_values(headers: dict[str, str]) -> None:
    for name, value in headers.items():
        if "\r" in value or "\n" in value:
            raise typer.BadParameter(
                f"Invalid value for header '{name}': control characters are not allowed."
            )
