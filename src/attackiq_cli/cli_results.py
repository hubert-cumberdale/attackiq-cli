from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, NoReturn

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import write_csv_records, write_json
from attackiq_cli.services import (
    ResultsMode,
    ServiceContext,
    build_auth_context,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import fetch_phase_logs as svc_fetch_phase_logs
from attackiq_cli.services import fetch_phase_results as svc_fetch_phase_results
from attackiq_cli.services import fetch_results_list as svc_fetch_results_list
from attackiq_cli.spec import SpecIndex

console = Console()

results_app = typer.Typer(
    help="Result commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "list_result_logs",
    "list_result_phases",
    "list_results",
    "results_app",
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


def _normalize_output_format(output_format: str) -> str:
    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")
    return fmt


def _validate_records_output_options(output_format: str, output: Path | None) -> str:
    fmt = _normalize_output_format(output_format)
    if fmt == "csv" and output is None:
        raise typer.BadParameter("CSV output requires --output.")
    return fmt


def _write_records_output(
    *,
    records: list[dict[str, Any]],
    output_format: str,
    output: Path | None,
    preferred_fields: tuple[str, ...] | list[str] | None = None,
) -> None:
    fmt = _validate_records_output_options(output_format, output)
    if fmt == "csv":
        if output is None:
            raise AssertionError("CSV output requires a destination path.")
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=preferred_fields)
        return

    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)


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


def _parse_results_mode(mode: str) -> ResultsMode:
    value = mode.strip().lower()
    try:
        return ResultsMode(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in ResultsMode)
        raise typer.BadParameter(f"mode must be one of: {choices}.") from exc


def _normalize_result_join_keys(
    result_summary_id: str | None,
    scenario_job_id: str | None,
) -> tuple[str | None, str | None]:
    cleaned_result_summary_id = result_summary_id.strip() if result_summary_id else None
    cleaned_scenario_job_id = scenario_job_id.strip() if scenario_job_id else None
    if bool(cleaned_result_summary_id) == bool(cleaned_scenario_job_id):
        raise typer.BadParameter(
            "Provide exactly one of --result-summary-id or --scenario-job-id."
        )
    return cleaned_result_summary_id, cleaned_scenario_job_id


def _handle_results_value_error(exc: ValueError) -> NoReturn:
    for line in str(exc).splitlines():
        console.print(f"[red]{line}[/red]")
    raise typer.Exit(code=1) from exc


def _normalize_optional_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@results_app.command("list")
def list_results(
    ctx: typer.Context,
    mode: Annotated[
        str,
        typer.Option("--mode", help="Result page type: summaries, phases, or logs."),
    ] = ResultsMode.SUMMARIES.value,
    output_format: Annotated[
        str,
        typer.Option("--output-format", help="Output format: json or csv."),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    page: Annotated[int, typer.Option("--page", help="Page number within results.")] = 1,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
    ] = 200,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Search query for phases/logs modes."),
    ] = None,
    tag_id: Annotated[
        str | None,
        typer.Option("--tag-id", help="Filter result summaries by tag ID."),
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
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    results_mode = _parse_results_mode(mode)
    search = search.strip() if search and search.strip() else None
    tag_id = _normalize_optional_filter(tag_id)
    if tag_id is not None and results_mode != ResultsMode.SUMMARIES:
        raise typer.BadParameter("tag-id is only supported for summaries mode.")

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records, _has_next = svc_fetch_results_list(
            context,
            mode=results_mode,
            page=page,
            page_size=page_size,
            search=search,
            insecure=insecure,
            timeout=timeout,
            tag_id=tag_id,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@results_app.command("phases")
def list_result_phases(
    ctx: typer.Context,
    result_summary_id: Annotated[
        str | None,
        typer.Option(
            "--result-summary-id",
            help="Result summary ID to join phase results by.",
        ),
    ] = None,
    scenario_job_id: Annotated[
        str | None,
        typer.Option("--scenario-job-id", help="Scenario job ID to join phase results by."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--output-format", help="Output format: json or csv."),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    page: Annotated[int, typer.Option("--page", help="Page number within results.")] = 1,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
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
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    result_summary_id, scenario_job_id = _normalize_result_join_keys(
        result_summary_id,
        scenario_job_id,
    )

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records = svc_fetch_phase_results(
            context,
            result_summary_id=result_summary_id,
            scenario_job_id=scenario_job_id,
            page=page,
            page_size=page_size,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@results_app.command("logs")
def list_result_logs(
    ctx: typer.Context,
    result_summary_id: Annotated[
        str | None,
        typer.Option("--result-summary-id", help="Result summary ID to join phase logs by."),
    ] = None,
    scenario_job_id: Annotated[
        str | None,
        typer.Option("--scenario-job-id", help="Scenario job ID to join phase logs by."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--output-format", help="Output format: json or csv."),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for JSON output (defaults to stdout).",
        ),
    ] = None,
    page: Annotated[int, typer.Option("--page", help="Page number within results.")] = 1,
    page_size: Annotated[
        int,
        typer.Option("--page-size", help="Number of results per page."),
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
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    result_summary_id, scenario_job_id = _normalize_result_join_keys(
        result_summary_id,
        scenario_job_id,
    )

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records = svc_fetch_phase_logs(
            context,
            result_summary_id=result_summary_id,
            scenario_job_id=scenario_job_id,
            page=page,
            page_size=page_size,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)
