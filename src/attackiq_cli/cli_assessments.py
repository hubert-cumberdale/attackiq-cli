from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import typer
from rich.console import Console

from attackiq_cli.cli_config import load_config_or_exit
from attackiq_cli.config import ConfigError, validate_timeout
from attackiq_cli.exporter import ASSESSMENT_FIELD_ORDER, write_csv_records, write_json
from attackiq_cli.mutation_plans import (
    build_create_assessment_from_scenarios_plan,
    build_create_assessment_from_template_plan,
    build_run_assessment_plan,
    build_update_assessment_defaults_plan,
)
from attackiq_cli.mutations import run_mutation_command
from attackiq_cli.services import (
    AssessmentFilters,
    ServiceContext,
    build_assessment_query_params,
    build_assessment_summary_records,
    build_auth_context,
    ensure_auth,
    fetch_assessment_detail,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import build_client as build_client
from attackiq_cli.services import (
    create_assessment_from_scenarios as svc_create_assessment_from_scenarios,
)
from attackiq_cli.services import (
    create_assessment_from_template as svc_create_assessment_from_template,
)
from attackiq_cli.services import list_assessments as svc_list_assessments
from attackiq_cli.services import run_assessment as svc_run_assessment
from attackiq_cli.services import (
    update_assessment_defaults as svc_update_assessment_defaults,
)
from attackiq_cli.spec import Operation, SpecIndex

console = Console()

assessments_app = typer.Typer(
    help="Assessment commands.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "AssessmentFilters",
    "assessments_app",
    "build_client",
    "create_assessment",
    "create_assessment_from_template",
    "list_assessments",
    "run_assessment",
    "show_assessment",
    "update_assessment_defaults",
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


def _load_uuid_list_from_text(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        parts = [item.strip() for item in cleaned.split(",") if item.strip()]
        items.extend(parts)
    return items


def _load_uuid_list_from_file(path: Path) -> list[str]:
    return _load_uuid_list_from_text(path.read_text(encoding="utf-8"))


def _stable_dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _run_mutation_command(
    ctx: typer.Context,
    *,
    apply: bool,
    operation: Operation,
    output: Path | None,
    timeout: float | None,
    apply_request: Callable[[ServiceContext, float | None], Any],
    index: SpecIndex | None = None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> None:
    run_mutation_command(
        apply=apply,
        operation=operation,
        output=output,
        prepare_context=lambda: _prepare_apply_context(
            ctx,
            operation=operation,
            timeout=timeout,
            index=index,
        ),
        apply_request=apply_request,
        handle_http_error=_print_http_error_and_exit,
        path_params=path_params,
        query_params=query_params,
        json_body=json_body,
        on_dry_run_file_written=lambda path: console.print(f"Response written to {path}"),
    )


def _prepare_apply_context(
    ctx: typer.Context,
    *,
    operation: Operation,
    timeout: float | None,
    index: SpecIndex | None = None,
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

    auth = build_auth_context(cfg, preferred_scheme="auto")
    try:
        warnings = ensure_auth(operation, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    if index is None:
        index = SpecIndex.from_file(ctx.obj["spec_path"])
    return ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index), timeout


@assessments_app.command("list")
def list_assessments(
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
            help="Destination file for JSON output (defaults to stdout).",
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
    search: Annotated[
        str | None,
        typer.Option("--search", help="Filter by name/description terms."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Filter by exact assessment name."),
    ] = None,
    asset_group_id: Annotated[
        list[str] | None,
        typer.Option(
            "--asset-group-id",
            help="Filter by asset group id(s) (repeat or comma-separated).",
        ),
    ] = None,
    blueprint_id: Annotated[
        str | None,
        typer.Option("--blueprint-id", help="Filter by blueprint id."),
    ] = None,
    execution_strategy: Annotated[
        int | None,
        typer.Option(
            "--execution-strategy",
            help="Filter by execution strategy (0=Prevention and Detection, 1=Prevention).",
        ),
    ] = None,
    has_default_schedule: Annotated[
        bool | None,
        typer.Option(
            "--has-default-schedule/--no-has-default-schedule",
            help="Filter by default schedule usage.",
        ),
    ] = None,
    id_in: Annotated[
        list[str] | None,
        typer.Option(
            "--id",
            "--id-in",
            help="Filter by assessment id(s) (repeat or comma-separated).",
        ),
    ] = None,
    report_instance_type: Annotated[
        str | None,
        typer.Option("--report-instance-type", help="Filter by report instance type."),
    ] = None,
    tag_id: Annotated[
        str | None,
        typer.Option("--tag-id", help="Filter by tag ID."),
    ] = None,
    tag_ids: Annotated[
        list[str] | None,
        typer.Option("--tag-ids", help="Filter by tag IDs (repeat or comma-separated)."),
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
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if page is not None and page < 1:
        raise typer.BadParameter("page must be >= 1.")

    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")
    if fmt == "csv" and output is None:
        raise typer.BadParameter("CSV output requires --output.")
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

    filters = AssessmentFilters(
        asset_group_id=asset_group_id,
        blueprint_id=blueprint_id,
        execution_strategy=execution_strategy,
        has_default_schedule=has_default_schedule,
        id__in=id_in,
        name=name,
        report_instance_type=report_instance_type,
        search=search,
        tag_id=tag_id,
        tag_ids=tag_ids,
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
    op = index.get_operation("v1_assessments_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        items = svc_list_assessments(
            context,
            page=page,
            page_size=page_size,
            query_params=query_params or None,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    if fmt == "json":
        if output is None:
            write_json(sys.stdout, items)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, items)
        return

    if output is None:
        raise typer.BadParameter("CSV output requires --output.")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = build_assessment_summary_records(items)
    write_csv_records(
        output,
        records,
        preferred_fields=ASSESSMENT_FIELD_ORDER,
        include_preferred_missing=True,
    )


@assessments_app.command("show")
def show_assessment(
    ctx: typer.Context,
    assessment_id: Annotated[str, typer.Argument(help="Assessment UUID.")],
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

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_assessments_retrieve")
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
        detail = fetch_assessment_detail(
            context,
            assessment_id=assessment_id,
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


@assessments_app.command("create")
def create_assessment(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Assessment name.")],
    scenario_id: Annotated[
        list[str] | None,
        typer.Option("--scenario-id", help="Scenario UUID to include (repeatable)."),
    ] = None,
    scenario_ids_file: Annotated[
        Path | None,
        typer.Option(
            "--scenario-ids-file",
            exists=True,
            readable=True,
            help="Text file containing scenario UUIDs (one per line or comma-separated).",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
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
    assessment_name = (name or "").strip()
    if not assessment_name:
        raise typer.BadParameter("--name is required.")

    requested: list[str] = []
    requested.extend([value for value in scenario_id or [] if value and value.strip()])
    if scenario_ids_file is not None:
        requested.extend(_load_uuid_list_from_file(scenario_ids_file))
    requested = _stable_dedup([value.strip() for value in requested if value.strip()])
    if not requested:
        raise typer.BadParameter("At least one --scenario-id (or --scenario-ids-file) is required.")

    scenario_ids = [_normalize_uuid(value, label="scenario-id") for value in requested]
    plan = build_create_assessment_from_scenarios_plan(
        name=assessment_name,
        scenario_ids=scenario_ids,
    )
    body = cast(dict[str, Any], plan.json_body)

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        json_body=plan.json_body,
        apply_request=lambda context, effective_timeout: svc_create_assessment_from_scenarios(
            context,
            name=body["name"],
            scenario_ids=body["scenario_ids"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@assessments_app.command("create-from-template")
def create_assessment_from_template(
    ctx: typer.Context,
    template_id: Annotated[str, typer.Option("--template-id", help="Assessment template UUID.")],
    name: Annotated[str, typer.Option("--name", help="Assessment name (project_name).")],
    blueprint_id: Annotated[
        str | None,
        typer.Option("--blueprint-id", help="Blueprint UUID."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
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
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    project_name = (name or "").strip()
    if not project_name:
        raise typer.BadParameter("--name is required.")
    plan = build_create_assessment_from_template_plan(
        index,
        template_id=_normalize_uuid(template_id, label="--template-id"),
        project_name=project_name,
        blueprint_id=(
            _normalize_uuid(blueprint_id, label="--blueprint-id")
            if blueprint_id is not None
            else None
        ),
    )
    body = cast(dict[str, Any], plan.json_body)

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        index=index,
        json_body=plan.json_body,
        apply_request=lambda context, effective_timeout: svc_create_assessment_from_template(
            context,
            template_id=body["template"],
            project_name=body["project_name"],
            blueprint_id=body.get("blueprint"),
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@assessments_app.command("update-defaults")
def update_assessment_defaults(
    ctx: typer.Context,
    assessment_id: Annotated[str, typer.Argument(help="Assessment UUID.")],
    asset_id: Annotated[
        list[str] | None,
        typer.Option(
            "--asset-id",
            help="Asset UUID to set as an assessment default target (repeatable).",
        ),
    ] = None,
    asset_ids_file: Annotated[
        Path | None,
        typer.Option(
            "--asset-ids-file",
            exists=True,
            readable=True,
            help="Text file containing asset UUIDs (one per line or comma-separated).",
        ),
    ] = None,
    asset_group_id: Annotated[
        list[str] | None,
        typer.Option(
            "--asset-group-id",
            help="Asset group UUID to set as an assessment default target (repeatable).",
        ),
    ] = None,
    asset_group_ids_file: Annotated[
        Path | None,
        typer.Option(
            "--asset-group-ids-file",
            exists=True,
            readable=True,
            help="Text file containing asset group UUIDs (one per line or comma-separated).",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
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
    requested_assets: list[str] = []
    requested_assets.extend([value for value in asset_id or [] if value and value.strip()])
    if asset_ids_file is not None:
        requested_assets.extend(_load_uuid_list_from_file(asset_ids_file))
    assets = [
        _normalize_uuid(value, label="asset-id")
        for value in _stable_dedup([value.strip() for value in requested_assets if value.strip()])
    ]

    requested_groups: list[str] = []
    requested_groups.extend([value for value in asset_group_id or [] if value and value.strip()])
    if asset_group_ids_file is not None:
        requested_groups.extend(_load_uuid_list_from_file(asset_group_ids_file))
    asset_groups = [
        _normalize_uuid(value, label="asset-group-id")
        for value in _stable_dedup([value.strip() for value in requested_groups if value.strip()])
    ]

    if not assets and not asset_groups:
        raise typer.BadParameter(
            "At least one --asset-id/--asset-ids-file or "
            "--asset-group-id/--asset-group-ids-file is required."
        )

    index = SpecIndex.from_file(ctx.obj["spec_path"])
    plan = build_update_assessment_defaults_plan(
        index,
        assessment_id=_normalize_uuid(assessment_id, label="assessment-id"),
        asset_ids=assets,
        asset_group_ids=asset_groups,
    )
    body = cast(dict[str, Any], plan.json_body)

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=plan.path_params,
        json_body=plan.json_body,
        apply_request=lambda context, effective_timeout: svc_update_assessment_defaults(
            context,
            assessment_id=plan.path_params["id"],
            assets=body.get("assets"),
            asset_groups=body.get("asset_groups"),
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@assessments_app.command("run")
def run_assessment(
    ctx: typer.Context,
    assessment_id: Annotated[str, typer.Argument(help="Assessment UUID.")],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Perform the network request (default is dry-run)."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write API response JSON to a file (otherwise stdout).",
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
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    plan = build_run_assessment_plan(
        index,
        assessment_id=_normalize_uuid(assessment_id, label="assessment-id"),
    )

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=plan.operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=plan.path_params,
        query_params=plan.query_params,
        apply_request=lambda context, effective_timeout: svc_run_assessment(
            context,
            assessment_id=plan.path_params["id"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )
