from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.client import paginate_results
from attackiq_cli.config import CliConfig, ConfigError, validate_timeout
from attackiq_cli.exporter import (
    ASSESSMENT_FIELD_ORDER,
    SCENARIO_EXPORT_FIELDS,
    TEST_FIELD_ORDER,
    apply_scenario_details,
    build_scenario_export_records,
    build_template_records,
    load_scenario_details,
    load_scenario_details_lenient,
    load_template_tests_index,
    resolve_format,
    write_csv_records,
    write_csv_templates,
    write_json,
)
from attackiq_cli.services import (
    AssessmentFilters,
    build_assessment_query_params,
    build_assessment_summary_records,
    build_auth_context,
    build_client,
    build_test_summary_records,
    ensure_auth,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.spec import SpecIndex

console = Console()

export_app = typer.Typer(
    help="Export common resources to CSV or JSON.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "export_app",
    "export_assessments",
    "export_scenarios",
    "export_templates",
    "export_tests",
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


def _resolve_config_and_base_url() -> tuple[CliConfig, str]:
    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)
    return cfg, base_url


def _validate_timeout(timeout: float | None) -> float | None:
    if timeout is None:
        return None
    try:
        return validate_timeout(timeout)
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc


@export_app.command("templates")
def export_templates(
    ctx: typer.Context,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Destination file (.csv or .json).",
        ),
    ] = Path("assessment_templates.csv"),
    file_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format. Defaults to file extension or csv."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Page size for API pagination."),
    ] = 200,
    include_empty: Annotated[
        bool,
        typer.Option("--include-empty", help="Include templates with no scenarios (CSV only)."),
    ] = False,
    scenario_details: Annotated[
        bool,
        typer.Option(
            "--scenario-details/--no-scenario-details",
            help="Fetch scenario names/types via per-ID lookups (slower, may skip failures).",
        ),
    ] = False,
    scenario_details_lenient: Annotated[
        bool,
        typer.Option(
            "--scenario-details-lenient/--scenario-details-strict",
            help="Continue if individual scenario lookups fail.",
        ),
    ] = False,
    scenario_details_retries: Annotated[
        int,
        typer.Option(
            "--scenario-details-retries",
            min=0,
            help="Retry attempts per scenario ID when --scenario-details-lenient is set.",
        ),
    ] = 0,
    scenario_concurrency: Annotated[
        int,
        typer.Option(
            "--scenario-concurrency",
            min=1,
            help="Max concurrent per-ID scenario lookups when --scenario-details is set.",
        ),
    ] = 4,
    insecure: Annotated[
        bool,
        typer.Option("--insecure", help="Disable TLS verification for this export."),
    ] = False,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = None,
) -> None:
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    cfg, base_url = _resolve_config_and_base_url()
    fmt = resolve_format(output, file_format)
    timeout = _validate_timeout(timeout)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    templates_op = index.get_operation("v1_assessment_templates_list")
    template_tests_op = index.get_operation("v1_project_template_tests_list")
    scenario_retrieve_op = index.get_operation("v1_scenarios_retrieve")
    try:
        warnings = ensure_auth(templates_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    try:
        with build_client(
            base_url,
            cfg,
            auth,
            insecure=insecure,
            timeout=timeout,
        ) as client:
            template_tests_index = load_template_tests_index(client, template_tests_op, page_size)
            templates, scenario_ids = build_template_records(
                client,
                templates_op,
                template_tests_index,
                page_size,
            )
            if scenario_details and scenario_ids:
                if scenario_details_lenient:
                    scenario_lookup, failures = load_scenario_details_lenient(
                        client,
                        scenario_retrieve_op,
                        scenario_ids,
                        max_workers=scenario_concurrency,
                        retries=scenario_details_retries,
                    )
                    apply_scenario_details(templates, scenario_lookup)
                    if failures:
                        console.print(
                            "[yellow]Scenario detail lookup failed for "
                            f"{len(failures)} IDs.[/yellow]"
                        )
                else:
                    scenario_lookup = load_scenario_details(
                        client,
                        scenario_retrieve_op,
                        scenario_ids,
                        max_workers=scenario_concurrency,
                    )
                    apply_scenario_details(templates, scenario_lookup)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        write_json(output, templates)
    else:
        write_csv_templates(output, templates, include_empty=include_empty)
    console.print(f"[green]Wrote {len(templates)} templates to {output} ({fmt}).[/green]")


@export_app.command("scenarios")
def export_scenarios(
    ctx: typer.Context,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Destination file (.csv or .json).",
        ),
    ] = Path("scenarios.csv"),
    file_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format. Defaults to file extension or csv."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Page size for API pagination."),
    ] = 200,
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
    cfg, base_url = _resolve_config_and_base_url()
    fmt = resolve_format(output, file_format)
    timeout = _validate_timeout(timeout)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    scenarios_op = index.get_operation("v1_scenarios_list")
    try:
        warnings = ensure_auth(scenarios_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    try:
        with build_client(
            base_url,
            cfg,
            auth,
            insecure=insecure,
            timeout=timeout,
        ) as client:
            scenarios = list(paginate_results(client, scenarios_op, page_size=page_size))
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        write_json(output, scenarios)
    else:
        records = build_scenario_export_records(scenarios)
        write_csv_records(
            output,
            records,
            preferred_fields=SCENARIO_EXPORT_FIELDS,
            include_preferred_missing=True,
            include_other_fields=False,
        )
    console.print(f"[green]Wrote {len(scenarios)} scenarios to {output} ({fmt}).[/green]")


@export_app.command("assessments")
def export_assessments(
    ctx: typer.Context,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Destination file (.csv or .json).",
        ),
    ] = Path("assessments.csv"),
    file_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format. Defaults to file extension or csv."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Page size for API pagination."),
    ] = 200,
    max_pages: Annotated[
        int | None,
        typer.Option("--max-pages", help="Maximum number of pages to fetch."),
    ] = None,
    asset_group_id: Annotated[
        list[str] | None,
        typer.Option(
            "--asset-group-id",
            help="Filter by asset group IDs (repeat or comma-separated).",
        ),
    ] = None,
    blueprint_id: Annotated[
        str | None,
        typer.Option("--blueprint-id", help="Filter by blueprint ID."),
    ] = None,
    execution_strategy: Annotated[
        int | None,
        typer.Option(
            "--execution-strategy",
            help="Execution strategy: 0=prevention+detection, 1=prevention.",
        ),
    ] = None,
    has_default_schedule: Annotated[
        bool | None,
        typer.Option(
            "--has-default-schedule/--no-has-default-schedule",
            help="Filter by default schedule usage.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Filter by exact assessment name."),
    ] = None,
    report_instance_type: Annotated[
        str | None,
        typer.Option("--report-instance-type", help="Filter by report instance type."),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Filter by name/description search terms."),
    ] = None,
    use_scenario_alert_rules: Annotated[
        bool | None,
        typer.Option(
            "--use-scenario-alert-rules/--no-use-scenario-alert-rules",
            help="Filter by scenario alert rules usage.",
        ),
    ] = None,
    version: Annotated[
        int | None,
        typer.Option("--version", help="Filter by assessment version."),
    ] = None,
    zones_ordering: Annotated[
        list[str] | None,
        typer.Option("--zones-ordering", help="Order by zone fields (repeat or comma-separated)."),
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
    cfg, base_url = _resolve_config_and_base_url()
    fmt = resolve_format(output, file_format)
    timeout = _validate_timeout(timeout)
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if max_pages is not None and max_pages < 1:
        raise typer.BadParameter("max-pages must be >= 1.")
    if execution_strategy is not None and execution_strategy not in {0, 1}:
        raise typer.BadParameter("execution-strategy must be 0 or 1.")
    filters = AssessmentFilters(
        asset_group_id=asset_group_id,
        blueprint_id=blueprint_id,
        execution_strategy=execution_strategy,
        has_default_schedule=has_default_schedule,
        name=name,
        report_instance_type=report_instance_type,
        search=search,
        use_scenario_alert_rules=use_scenario_alert_rules,
        version=version,
        zones_ordering=zones_ordering,
    )
    try:
        query_params = build_assessment_query_params(filters)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    assessments_op = index.get_operation("v1_assessments_list")
    try:
        warnings = ensure_auth(assessments_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    try:
        with build_client(
            base_url,
            cfg,
            auth,
            insecure=insecure,
            timeout=timeout,
        ) as client:
            assessments = list(
                paginate_results(
                    client,
                    assessments_op,
                    page_size=page_size,
                    max_pages=max_pages,
                    query_params=query_params or None,
                )
            )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        write_json(output, assessments)
    else:
        records = build_assessment_summary_records(assessments)
        write_csv_records(
            output,
            records,
            preferred_fields=ASSESSMENT_FIELD_ORDER,
            include_preferred_missing=True,
        )
    console.print(f"[green]Wrote {len(assessments)} assessments to {output} ({fmt}).[/green]")


@export_app.command("tests")
def export_tests(
    ctx: typer.Context,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Destination file (.csv or .json).",
        ),
    ] = Path("tests.csv"),
    file_format: Annotated[
        str | None,
        typer.Option("--format", help="Output format. Defaults to file extension or csv."),
    ] = None,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Page size for API pagination."),
    ] = 200,
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
    cfg, base_url = _resolve_config_and_base_url()
    fmt = resolve_format(output, file_format)
    timeout = _validate_timeout(timeout)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    tests_op = index.get_operation("v1_tests_list")
    try:
        warnings = ensure_auth(tests_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    try:
        with build_client(
            base_url,
            cfg,
            auth,
            insecure=insecure,
            timeout=timeout,
        ) as client:
            tests = list(paginate_results(client, tests_op, page_size=page_size))
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        write_json(output, tests)
    else:
        records = build_test_summary_records(tests)
        write_csv_records(output, records, preferred_fields=TEST_FIELD_ORDER)
    console.print(f"[green]Wrote {len(tests)} tests to {output} ({fmt}).[/green]")
