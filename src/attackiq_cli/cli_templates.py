from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import (
    TEMPLATE_FIELD_ORDER,
    TEMPLATE_TEST_FIELD_ORDER,
    write_csv_records,
    write_json,
)
from attackiq_cli.services import (
    ServiceContext,
    TemplateFilters,
    TemplateTestFilters,
    build_auth_context,
    build_template_summary_records,
    build_template_test_summary_records,
    ensure_auth,
    fetch_template_detail,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import list_template_tests as svc_list_template_tests
from attackiq_cli.services import list_templates as svc_list_templates
from attackiq_cli.spec import SpecIndex

console = Console()

templates_app = typer.Typer(
    help="Assessment template commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "list_template_tests",
    "list_templates",
    "show_template",
    "templates_app",
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


@templates_app.command("list")
def list_templates(
    ctx: typer.Context,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Assessment template search query."),
    ] = None,
    template_name: Annotated[
        str | None,
        typer.Option("--template-name", help="Exact assessment template name filter."),
    ] = None,
    project_name: Annotated[
        str | None,
        typer.Option("--project-name", help="Exact generated project name filter."),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", help="Assessment template category."),
    ] = None,
    assessment_type: Annotated[
        str | None,
        typer.Option("--assessment-type", help="Assessment template type filter."),
    ] = None,
    behavior: Annotated[
        str | None,
        typer.Option("--behavior", help="Behavior filter."),
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
    op = index.get_operation("v1_assessment_templates_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    filters = TemplateFilters(
        search=search,
        template_name=template_name,
        project_name=project_name,
        category=category,
        assessment_type=assessment_type,
        behavior=behavior,
    )
    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        templates = svc_list_templates(
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
        records = build_template_summary_records(templates)
        write_csv_records(output, records, preferred_fields=TEMPLATE_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, templates)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, templates)


@templates_app.command("show")
def show_template(
    ctx: typer.Context,
    template_id: Annotated[
        str,
        typer.Argument(help="Assessment template UUID."),
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
    op = index.get_operation("v1_assessment_templates_retrieve")
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
        detail = fetch_template_detail(
            context,
            template_id=template_id,
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


@templates_app.command("tests")
def list_template_tests(
    ctx: typer.Context,
    template_id: Annotated[
        str | None,
        typer.Option(
            "--template-id",
            "--project-template-id",
            help="Filter by assessment template UUID.",
        ),
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
    op = index.get_operation("v1_project_template_tests_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    filters = TemplateTestFilters(project_template_id=template_id)
    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        template_tests = svc_list_template_tests(
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
        records = build_template_test_summary_records(template_tests)
        write_csv_records(output, records, preferred_fields=TEMPLATE_TEST_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, template_tests)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, template_tests)
