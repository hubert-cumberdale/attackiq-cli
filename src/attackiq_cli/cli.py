from __future__ import annotations

import contextlib
import csv
import json
import os
import re
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, TextIO, cast

import httpx
import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from attackiq_cli import __version__
from attackiq_cli.backup import (
    BackupError,
    ConfigBackupOptions,
    normalize_backup_domains,
    run_configuration_backup,
)
from attackiq_cli.catalog import (
    CATALOG_CSV_FIELDS,
    DEFAULT_CATALOG_PATH,
    VALID_PROVIDERS,
    VALID_SCENARIO_STATUS,
    VALID_SURFACE,
    CatalogError,
    build_catalog_coverage_summary,
    catalog_records_for_csv,
    filter_catalog_records,
    load_bas_catalog,
    normalize_catalog_records,
    validate_bas_catalog,
)
from attackiq_cli.client import paginate_results, redact_headers, render_path
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
from attackiq_cli.exporter import (
    ASSESSMENT_FIELD_ORDER,
    ASSET_FIELD_ORDER,
    ASSET_GROUP_FIELD_ORDER,
    BLUEPRINT_FIELD_ORDER,
    INTEGRATION_CONNECTOR_FIELD_ORDER,
    SCENARIO_EXPORT_FIELDS,
    SCENARIO_FIELD_ORDER,
    SOURCE_TYPE_FIELD_ORDER,
    TEMPLATE_FIELD_ORDER,
    TEMPLATE_TEST_FIELD_ORDER,
    TEST_FIELD_ORDER,
    apply_scenario_details,
    build_scenario_export_records,
    build_template_records,
    fieldnames_for_records,
    load_scenario_details,
    load_scenario_details_lenient,
    load_template_tests_index,
    normalize_csv_value,
    resolve_format,
    write_csv_records,
    write_csv_templates,
    write_json,
)
from attackiq_cli.joiner import cli as joiner_cli
from attackiq_cli.logging_utils import setup_logging
from attackiq_cli.mutations import (
    run_mutation_command,
    write_json_payload,
)
from attackiq_cli.scenario_wizard import (
    ScenarioWizardError,
    apply_scenario_wizard_create,
    apply_scenario_wizard_package,
    build_runtime_prepare_from_image_tar_plan,
    build_runtime_prepare_plan,
    build_scenario_wizard_create_plan,
    build_scenario_wizard_package_plan,
    inspect_scenario_wizard_zip,
    prepare_runtime_bundle_from_bundle,
    prepare_runtime_bundle_from_image_tar,
    scenario_wizard_cache_dir,
    validate_runtime_bundle,
)
from attackiq_cli.services import (
    AssessmentFilters,
    AssetFilters,
    AssetGroupFilters,
    BlueprintFilters,
    IntegrationConnectorFilters,
    ResultsMode,
    ScenarioFilters,
    ServiceContext,
    SourceTypeFilters,
    TagFilters,
    TemplateFilters,
    TemplateTestFilters,
    TestFilters,
    ValidationResultFilters,
    build_assessment_query_params,
    build_assessment_summary_records,
    build_asset_group_summary_records,
    build_asset_query_params,
    build_asset_summary_records,
    build_auth_context,
    build_blueprint_summary_records,
    build_client,
    build_det_pipeline_create_assessment_operation,
    build_integration_connector_query_params,
    build_integration_connector_summary_records,
    build_scenario_summary_records,
    build_scenario_template_upload_operation,
    build_source_type_summary_records,
    build_tag_summary_records,
    build_template_summary_records,
    build_template_test_summary_records,
    build_test_query_params,
    build_test_summary_records,
    ensure_auth,
    fetch_assessment_detail,
    fetch_asset_detail,
    fetch_asset_group_detail,
    fetch_scenario_detail,
    fetch_tag_detail,
    fetch_template_detail,
    fetch_test_detail,
    normalize_api_backend,
    resolve_base_url,
    warn_if_insecure_base_url,
)
from attackiq_cli.services import (
    add_scenarios_to_test as svc_add_scenarios_to_test,
)
from attackiq_cli.services import (
    create_assessment_from_scenarios as svc_create_assessment_from_scenarios,
)
from attackiq_cli.services import (
    create_assessment_from_template as svc_create_assessment_from_template,
)
from attackiq_cli.services import (
    create_test as svc_create_test,
)
from attackiq_cli.services import (
    fetch_phase_logs as svc_fetch_phase_logs,
)
from attackiq_cli.services import (
    fetch_phase_results as svc_fetch_phase_results,
)
from attackiq_cli.services import (
    fetch_results_list as svc_fetch_results_list,
)
from attackiq_cli.services import (
    fetch_validation_result_executions as svc_fetch_validation_result_executions,
)
from attackiq_cli.services import (
    fetch_validation_results as svc_fetch_validation_results,
)
from attackiq_cli.services import (
    get_test_status as svc_get_test_status,
)
from attackiq_cli.services import (
    list_assessments as svc_list_assessments,
)
from attackiq_cli.services import (
    list_asset_groups as svc_list_asset_groups,
)
from attackiq_cli.services import (
    list_assets as svc_list_assets,
)
from attackiq_cli.services import (
    list_blueprints as svc_list_blueprints,
)
from attackiq_cli.services import (
    list_integration_connectors as svc_list_integration_connectors,
)
from attackiq_cli.services import (
    list_scenarios as svc_list_scenarios,
)
from attackiq_cli.services import (
    list_source_types as svc_list_source_types,
)
from attackiq_cli.services import (
    list_tags as svc_list_tags,
)
from attackiq_cli.services import (
    list_template_tests as svc_list_template_tests,
)
from attackiq_cli.services import (
    list_templates as svc_list_templates,
)
from attackiq_cli.services import (
    list_tests as svc_list_tests,
)
from attackiq_cli.services import (
    run_assessment as svc_run_assessment,
)
from attackiq_cli.services import (
    search_tags as svc_search_tags,
)
from attackiq_cli.services import (
    update_assessment_defaults as svc_update_assessment_defaults,
)
from attackiq_cli.spec import Operation, SpecIndex
from attackiq_cli.utils import (
    coerce_value_from_schema,
    load_json_payload,
    parse_key_value_pairs,
    validate_json_payload,
)

console = Console()
default_spec_path = Path(__file__).resolve().parent / "openapi.yaml"
COMPLETION_SHELL_ALIASES = {
    "bash": "bash",
    "fish": "fish",
    "powershell": "powershell",
    "powershell.exe": "powershell",
    "pwsh": "pwsh",
    "pwsh.exe": "pwsh",
    "zsh": "zsh",
}


def _completion_shell_from_env() -> str | None:
    raw = os.getenv("ATTACKIQ_COMPLETION_SHELL") or os.getenv("SHELL") or ""
    shell_name = Path(raw).name.lower()
    return COMPLETION_SHELL_ALIASES.get(shell_name)


def _patch_typer_completion_shell_detection() -> None:
    try:
        import typer.completion as typer_completion
    except ImportError:  # pragma: no cover - Typer is a required dependency.
        return

    shellingham = getattr(typer_completion, "shellingham", None)
    if shellingham is None or getattr(shellingham, "_attackiq_env_shell_fallback", False):
        return

    original_detect_shell = shellingham.detect_shell

    def detect_shell_with_env_fallback(*args: Any, **kwargs: Any) -> tuple[str, str | None]:
        if env_shell := _completion_shell_from_env():
            return env_shell, None
        return cast(tuple[str, str | None], original_detect_shell(*args, **kwargs))

    shellingham.detect_shell = detect_shell_with_env_fallback
    shellingham._attackiq_env_shell_fallback = True


_patch_typer_completion_shell_detection()

def _typer(**kwargs: Any) -> typer.Typer:
    return typer.Typer(pretty_exceptions_show_locals=False, **kwargs)


app = _typer(add_completion=True, no_args_is_help=True)
spec_app = _typer(help="Inspect the bundled OpenAPI specification.")
config_app = _typer(help="Configure defaults (base URL, timeouts, TLS).")
auth_app = _typer(help="Manage authentication tokens.")
export_app = _typer(help="Export common resources to CSV or JSON.")
backup_app = _typer(help="Backup redacted tenant configuration.")
catalog_app = _typer(help="Inspect local BAS scenario catalogs.")
scenario_wizard_app = _typer(help="Scenario Wizard local workflow helpers.")
scenario_wizard_runtime_app = _typer(help="Inspect and prepare Scenario Wizard runtimes.")
scenarios_app = _typer(help="Scenario commands.")
tags_app = _typer(help="Tag commands.")
templates_app = _typer(help="Assessment template commands.")
platform_api_app = _typer(help="Experimental aiq-platform-api parity helpers.")
build_app = _typer(help="Build request payloads and call plans (no network).")
build_assessment_app = _typer(help="Assessment build helpers.")
build_test_app = _typer(help="Test build helpers.")
assessments_app = _typer(help="Assessment commands.")
tests_app = _typer(help="Test commands.")
assets_app = _typer(help="Asset commands.")
asset_groups_app = _typer(help="Asset group commands.")
blueprints_app = _typer(help="Blueprint commands.")
integrations_app = _typer(help="Integration connector commands.")
source_types_app = _typer(help="Source type commands.")
results_app = _typer(help="Result commands.")
validation_results_app = _typer(help="Validation result commands.")

app.add_typer(spec_app, name="spec")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")
app.add_typer(export_app, name="export")
app.add_typer(backup_app, name="backup")
app.add_typer(catalog_app, name="catalog")
app.add_typer(scenario_wizard_app, name="scenario-wizard")
app.add_typer(scenarios_app, name="scenarios")
app.add_typer(tags_app, name="tags")
app.add_typer(templates_app, name="templates")
app.add_typer(platform_api_app, name="platform-api")
app.add_typer(assessments_app, name="assessments")
app.add_typer(tests_app, name="tests")
app.add_typer(assets_app, name="assets")
app.add_typer(asset_groups_app, name="asset-groups")
app.add_typer(blueprints_app, name="blueprints")
app.add_typer(integrations_app, name="integrations")
app.add_typer(source_types_app, name="source-types")
app.add_typer(results_app, name="results")
app.add_typer(validation_results_app, name="validation-results")
app.add_typer(build_app, name="build")
build_app.add_typer(build_assessment_app, name="assessment")
build_app.add_typer(build_test_app, name="test")
scenario_wizard_app.add_typer(scenario_wizard_runtime_app, name="runtime")


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


def version_callback(value: bool) -> None:
    if value:
        console.print(f"attackiq-cli version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        is_flag=True,
        help="Show version and exit.",
    ),
    spec_path: Path = typer.Option(
        default_spec_path,
        "--spec-path",
        envvar="ATTACKIQ_OPENAPI_PATH",
        exists=True,
        readable=True,
        help="Path to the OpenAPI 3.0 schema to load.",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["spec_path"] = spec_path


def load_config_or_exit() -> CliConfig:
    try:
        return load_config()
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def warn_if_insecure(base_url: str) -> None:
    if warn_if_insecure_base_url(base_url):
        console.print("[yellow]Warning: Base URL uses http:// (TLS disabled).[/yellow]")


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


def _print_call_hint(
    *, operation_id: str, output: Path | None, path_params: dict[str, Any] | None = None
) -> None:
    parts = ["attackiq", "call", operation_id]
    for key, value in sorted((path_params or {}).items()):
        parts.extend(["--param", f"{key}={value}"])
    if output is not None:
        parts.extend(["--body-file", str(output)])
    else:
        parts.extend(["--body", "<JSON>"])
    typer.secho("Suggested call:", err=True, fg=typer.colors.YELLOW)
    typer.secho(" ".join(parts), err=True, fg=typer.colors.YELLOW)


def _write_json_to_output(output: Path | None, payload: Any) -> None:
    write_json_payload(
        output,
        payload,
        on_file_written=lambda path: console.print(f"Response written to {path}"),
    )


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
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Destination directory for redacted backup artifacts.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Number of records per API page."),
    max_pages: int | None = typer.Option(
        None,
        "--max-pages",
        help="Maximum pages per paginated endpoint.",
    ),
    company_id: str | None = typer.Option(
        None,
        "--company-id",
        help="Company UUID to use when deriving source-type backups.",
    ),
    include: str | None = typer.Option(
        None,
        "--include",
        help="Comma-separated domains to include. Defaults to integrations,source-types,"
        "detection-rules.",
    ),
    endpoint_catalog: Path | None = typer.Option(
        None,
        "--endpoint-catalog",
        exists=True,
        readable=True,
        help="Sanitized endpoint catalog JSON for reviewed discovered endpoints.",
    ),
    tenant_alias: str = typer.Option(
        "unspecified",
        "--tenant-alias",
        help="Operator-safe tenant alias to record in the manifest.",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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


@platform_api_app.command("parity")
def platform_api_parity(
    ctx: typer.Context,
    resource: str = typer.Argument(..., help="Read-only resource to compare: scenarios or assets."),
    search: str | None = typer.Option(None, "--search", help="Search query for both backends."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    page_size: int = typer.Option(20, "--page-size", help="Number of results per backend page."),
    order_by: str | None = typer.Option(
        None,
        "--order-by",
        help="Ordering field for scenarios, or asset ordering when --resource assets.",
    ),
    deployment_state_id: int | None = typer.Option(
        None,
        "--deployment-state-id",
        help="Asset deployment state filter; valid only for assets.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for parity JSON (defaults to stdout).",
    ),
    fail_on_mismatch: bool = typer.Option(
        False,
        "--fail-on-mismatch/--no-fail-on-mismatch",
        help="Exit non-zero when native and platform-api IDs differ.",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)

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


@build_assessment_app.command("from-template")
def build_assessment_from_template(
    ctx: typer.Context,
    template_id: str = typer.Option(..., "--template-id", help="Assessment template UUID."),
    name: str = typer.Option(..., "--name", help="Assessment name (project_name)."),
    blueprint_id: str | None = typer.Option(None, "--blueprint-id", help="Blueprint UUID."),
    output: Path | None = typer.Option(
        None, "--output", help="Write payload JSON to a file (otherwise stdout)."
    ),
    print_call: bool = typer.Option(
        False, "--print-call", help="Print a suggested `attackiq call ...` command to stderr."
    ),
    strict_spec: bool = typer.Option(
        False,
        "--strict-spec",
        help="Fail if the payload does not validate against the bundled OpenAPI schema.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_assessments_project_from_template_create")
    body: dict[str, Any] = {
        "template": _normalize_uuid(template_id, label="--template-id"),
        "project_name": (name or "").strip(),
    }
    if not body["project_name"]:
        raise typer.BadParameter("--name is required.")
    if blueprint_id is not None:
        body["blueprint"] = _normalize_uuid(blueprint_id, label="--blueprint-id")

    # Validate against the spec when possible. This endpoint's spec is generally consistent.
    schema = index.request_body_schema(op)
    if schema:
        errors = validate_json_payload(body, schema, index.resolve_schema)
        if errors:
            message = "Payload does not match spec:\n" + "\n".join(f"- {err}" for err in errors)
            if strict_spec:
                raise typer.BadParameter(message)
            typer.secho(message, err=True, fg=typer.colors.YELLOW)

    if output is None:
        write_json(sys.stdout, body)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, body)
    if print_call:
        _print_call_hint(operation_id=op.operation_id, output=output)


@build_test_app.command("create")
def build_test_create(
    ctx: typer.Context,
    assessment_id: str = typer.Option(..., "--assessment-id", help="Assessment UUID."),
    name: str = typer.Option(..., "--name", help="Test name."),
    output: Path | None = typer.Option(
        None, "--output", help="Write payload JSON to a file (otherwise stdout)."
    ),
    print_call: bool = typer.Option(
        False, "--print-call", help="Print a suggested `attackiq call ...` command to stderr."
    ),
    strict_spec: bool = typer.Option(
        False,
        "--strict-spec",
        help="Fail if the payload does not validate against the bundled OpenAPI schema.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_create")

    # The bundled schema for v1_tests_create currently marks fields like cron_expression/insights
    # as required, but the API examples show only project+name. We enforce minimal invariants
    # here and only use spec validation as an optional strict gate.
    body: dict[str, Any] = {
        "project": _normalize_uuid(assessment_id, label="--assessment-id"),
        "name": (name or "").strip(),
    }
    if not body["name"]:
        raise typer.BadParameter("--name is required.")

    schema = index.request_body_schema(op)
    if strict_spec and schema:
        errors = validate_json_payload(body, schema, index.resolve_schema)
        if errors:
            message = "Payload does not match spec:\n" + "\n".join(f"- {err}" for err in errors)
            raise typer.BadParameter(message)

    if output is None:
        write_json(sys.stdout, body)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, body)
    if print_call:
        _print_call_hint(operation_id=op.operation_id, output=output)


@build_test_app.command("add-scenarios")
def build_test_add_scenarios(
    ctx: typer.Context,
    test_id: str = typer.Argument(..., help="Test UUID."),
    scenario_id: list[str] = typer.Option(
        [], "--scenario-id", help="Scenario UUID to include (repeatable)."
    ),
    scenario_ids_file: Path | None = typer.Option(
        None,
        "--scenario-ids-file",
        exists=True,
        readable=True,
        help="Text file containing scenario UUIDs (one per line or comma-separated).",
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write payload JSON to a file (otherwise stdout)."
    ),
    print_call: bool = typer.Option(
        False, "--print-call", help="Print a suggested `attackiq call ...` command to stderr."
    ),
    strict_spec: bool = typer.Option(
        False,
        "--strict-spec",
        help="Fail if the payload does not validate against the bundled OpenAPI schema.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_bulk_add_scenarios_create")

    requested: list[str] = []
    requested.extend([value for value in scenario_id if value and value.strip()])
    if scenario_ids_file is not None:
        requested.extend(_load_uuid_list_from_file(scenario_ids_file))
    requested = _stable_dedup([value.strip() for value in requested if value.strip()])
    if not requested:
        raise typer.BadParameter("At least one --scenario-id (or --scenario-ids-file) is required.")

    include = [_normalize_uuid(value, label="scenario-id") for value in requested]
    path_params = {"id": _normalize_uuid(test_id, label="test-id")}
    body: dict[str, Any] = {"include": include}

    # The bundled schema for this endpoint is inconsistent (it points at the test serializer).
    # We still allow strict validation if desired, but default to a minimal payload.
    schema = index.request_body_schema(op)
    if strict_spec and schema:
        errors = validate_json_payload(body, schema, index.resolve_schema)
        if errors:
            message = "Payload does not match spec:\n" + "\n".join(f"- {err}" for err in errors)
            raise typer.BadParameter(message)

    if output is None:
        write_json(sys.stdout, body)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, body)
    if print_call:
        _print_call_hint(operation_id=op.operation_id, output=output, path_params=path_params)


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


def render_operations_table(
    operations: list[Operation],
    *,
    title: str = "Operations",
    fields: list[str] | None = None,
) -> Table:
    table = Table(title=title, box=box.MINIMAL_DOUBLE_HEAD)
    field_map = {
        "operation_id": ("OperationId", lambda op: op.operation_id),
        "method": ("Method", lambda op: op.method.upper()),
        "path": ("Path", lambda op: op.path),
        "summary": ("Summary", lambda op: op.summary or "-"),
        "tags": ("Tags", lambda op: ", ".join(op.tags)),
    }
    selected_fields = fields or ["operation_id", "method", "path", "tags"]
    for field in selected_fields:
        label, _getter = field_map[field]
        table.add_column(label)
    for op in operations:
        row = []
        for field in selected_fields:
            _label, getter = field_map[field]
            row.append(getter(op))
        table.add_row(*row)
    return table


def normalize_spec_fields(raw_fields: str | None, *, default: list[str]) -> list[str]:
    allowed = {"operation_id", "method", "path", "summary", "tags"}
    if raw_fields is None:
        return default
    fields = []
    for entry in raw_fields.split(","):
        cleaned = entry.strip().lower().replace("-", "_")
        if not cleaned:
            continue
        if cleaned not in allowed:
            raise typer.BadParameter(
                "fields must be: operation_id, method, path, summary, tags."
            )
        fields.append(cleaned)
    if not fields:
        raise typer.BadParameter(
            "fields must include at least one of: operation_id, method, path, summary, tags."
        )
    return fields


def slice_operations(
    operations: list[Operation], *, limit: int | None, offset: int
) -> list[Operation]:
    if offset < 0:
        raise typer.BadParameter("offset must be >= 0.")
    if limit is not None and limit <= 0:
        raise typer.BadParameter("limit must be >= 1.")
    if offset:
        operations = operations[offset:]
    if limit is not None:
        operations = operations[:limit]
    return operations


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


def _load_bas_catalog_or_exit(path: Path):
    try:
        return load_bas_catalog(path)
    except (CatalogError, OSError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@catalog_app.command("validate")
def validate_catalog(
    path: Path = typer.Option(
        DEFAULT_CATALOG_PATH,
        "--path",
        "-p",
        help="BAS catalog root containing a scenarios directory.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for validation JSON (defaults to stdout).",
    ),
) -> None:
    """Validate a local BAS catalog without network access."""
    catalog = _load_bas_catalog_or_exit(path)
    payload = validate_bas_catalog(catalog)
    _write_json_to_output(output, payload)
    if not payload["valid"]:
        raise typer.Exit(code=1)


@catalog_app.command("list")
def list_catalog_records(
    path: Path = typer.Option(
        DEFAULT_CATALOG_PATH,
        "--path",
        "-p",
        help="BAS catalog root containing a scenarios directory.",
    ),
    provider: str | None = typer.Option(None, "--provider", help="Filter by provider: aws|azure."),
    status: str | None = typer.Option(
        None,
        "--status",
        help="Filter by source catalog status: proposed|validated|lab_only.",
    ),
    technique: str | None = typer.Option(None, "--technique", help="Filter by ATT&CK ID."),
    surface: str | None = typer.Option(None, "--surface", help="Filter by surface such as IAM."),
    search: str | None = typer.Option(None, "--search", help="Case-insensitive text search."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of records to return."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for output (CSV requires --output).",
    ),
) -> None:
    """List normalized records from a local BAS catalog."""
    if provider and provider.lower() not in VALID_PROVIDERS:
        raise typer.BadParameter("provider must be one of: aws, azure.")
    if status and status.lower() not in VALID_SCENARIO_STATUS:
        raise typer.BadParameter("status must be one of: proposed, validated, lab_only.")
    if surface and surface.upper() not in VALID_SURFACE:
        raise typer.BadParameter("surface must be a valid BAS catalog surface.")
    if limit is not None and limit < 1:
        raise typer.BadParameter("limit must be >= 1.")
    fmt = output_format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("output-format must be json or csv.")

    catalog = _load_bas_catalog_or_exit(path)
    records = filter_catalog_records(
        normalize_catalog_records(catalog),
        provider=provider,
        status=status,
        technique=technique,
        surface=surface,
        search=search,
        limit=limit,
    )

    if fmt == "csv":
        if output is None:
            typer.secho("CSV output requires --output.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(
            output,
            catalog_records_for_csv(records),
            preferred_fields=CATALOG_CSV_FIELDS,
        )
        return
    _write_json_to_output(output, records)


@catalog_app.command("coverage")
def summarize_catalog_coverage(
    path: Path = typer.Option(
        DEFAULT_CATALOG_PATH,
        "--path",
        "-p",
        help="BAS catalog root containing a scenarios directory.",
    ),
    include_techniques: bool = typer.Option(
        False,
        "--include-techniques",
        help="Include per-technique scenario detail in the JSON output.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for coverage JSON (defaults to stdout).",
    ),
) -> None:
    """Summarize coverage for a local BAS catalog."""
    catalog = _load_bas_catalog_or_exit(path)
    payload = build_catalog_coverage_summary(catalog)
    if not include_techniques:
        payload = dict(payload)
        payload.pop("techniques", None)
    _write_json_to_output(output, payload)


@scenario_wizard_runtime_app.command("inspect")
def inspect_scenario_wizard_runtime(
    zip_path: Path = typer.Option(
        ...,
        "--zip",
        help="Scenario Wizard wrapper zip to inspect.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Scenario Wizard runtime cache root (defaults to user cache).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for inspection JSON (defaults to stdout).",
    ),
) -> None:
    """Inspect Scenario Wizard wrapper metadata and local runtime bundle status."""
    try:
        payload = inspect_scenario_wizard_zip(zip_path, cache_dir=cache_dir)
    except ScenarioWizardError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    payload["default_cache_dir"] = str(scenario_wizard_cache_dir())
    _write_json_to_output(output, payload)


@scenario_wizard_runtime_app.command("validate")
def validate_scenario_wizard_runtime(
    bundle: Path = typer.Option(
        ...,
        "--bundle",
        help="Scenario Wizard runtime bundle directory to validate.",
    ),
    wizard_version: str | None = typer.Option(
        None,
        "--wizard-version",
        help="Expected Scenario Wizard wrapper version.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for validation JSON (defaults to stdout).",
    ),
) -> None:
    """Validate a local Scenario Wizard runtime bundle manifest and required files."""
    payload = validate_runtime_bundle(bundle, expected_wizard_version=wizard_version)
    _write_json_to_output(output, payload)
    if not payload["valid"]:
        raise typer.Exit(code=1)


@scenario_wizard_runtime_app.command("prepare")
def prepare_scenario_wizard_runtime(
    from_bundle: Path | None = typer.Option(
        None,
        "--from-bundle",
        help="Validated Scenario Wizard runtime bundle directory to copy into the local cache.",
    ),
    from_image_tar: Path | None = typer.Option(
        None,
        "--from-image-tar",
        help="Docker image filesystem/save tar to convert into a runtime bundle.",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="Scenario Wizard runtime cache root (defaults to user cache).",
    ),
    wizard_version: str | None = typer.Option(
        None,
        "--wizard-version",
        help="Expected Scenario Wizard wrapper version and destination cache key.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace an existing cached runtime bundle at the destination path.",
    ),
    runtime_root: str | None = typer.Option(
        None,
        "--runtime-root",
        help="Path inside image tar containing scenario_wizard.sh (auto-detected by default).",
    ),
    wheelhouse_path: str | None = typer.Option(
        None,
        "--wheelhouse-path",
        help="Path inside image tar containing runtime wheels (auto-detected by default).",
    ),
    requirements_path: str | None = typer.Option(
        None,
        "--requirements-path",
        help="Path inside image tar containing runtime requirements (auto-detected by default).",
    ),
    python_version: str = typer.Option(
        "3.12",
        "--python-version",
        help="Python version target to record in image-tar runtime manifests.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Preview by default; --apply copies the validated bundle into the cache.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for prepare plan/result JSON (defaults to stdout).",
    ),
) -> None:
    """Prepare a local Scenario Wizard runtime bundle from explicit trusted artifacts."""
    source_count = int(from_bundle is not None) + int(from_image_tar is not None)
    if source_count != 1:
        raise typer.BadParameter("Provide exactly one source: --from-bundle or --from-image-tar.")
    if dry_run:
        if from_bundle is not None:
            payload = build_runtime_prepare_plan(
                from_bundle,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
            )
        else:
            assert from_image_tar is not None
            payload = build_runtime_prepare_from_image_tar_plan(
                from_image_tar,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
                runtime_root=runtime_root,
                wheelhouse_path=wheelhouse_path,
                requirements_path=requirements_path,
                python_version=python_version,
            )
        _write_json_to_output(output, payload)
        if not payload["ready"]:
            raise typer.Exit(code=1)
        return
    try:
        if from_bundle is not None:
            payload = prepare_runtime_bundle_from_bundle(
                from_bundle,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
            )
        else:
            assert from_image_tar is not None
            payload = prepare_runtime_bundle_from_image_tar(
                from_image_tar,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
                runtime_root=runtime_root,
                wheelhouse_path=wheelhouse_path,
                requirements_path=requirements_path,
                python_version=python_version,
            )
    except ScenarioWizardError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _write_json_to_output(output, payload)
    if not payload["prepared"]:
        raise typer.Exit(code=1)


@scenario_wizard_app.command("create")
def plan_scenario_wizard_create(
    config: Path = typer.Option(
        ...,
        "--config",
        help="Scenario Wizard scenario_configuration.json file.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output",
        help="Directory where Scenario Wizard would create the generated scenario.",
    ),
    runtime_bundle: Path = typer.Option(
        ...,
        "--runtime-bundle",
        help="Validated local Scenario Wizard runtime bundle directory.",
    ),
    wizard_version: str | None = typer.Option(
        None,
        "--wizard-version",
        help="Expected Scenario Wizard wrapper version.",
    ),
    python_executable: str = typer.Option(
        "python3.12",
        "--python",
        help="Python executable planned for the local Scenario Wizard virtual environment.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow the plan to target an existing generated scenario path.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Preview by default; --apply runs the validated local runtime.",
    ),
    timeout: float = typer.Option(
        300.0,
        "--timeout",
        help="Timeout in seconds for each local create subprocess.",
    ),
    plan_output: Path | None = typer.Option(
        None,
        "--plan-output",
        help="Destination file for dry-run plan or apply result JSON (defaults to stdout).",
    ),
) -> None:
    """Plan or run a no-container Scenario Wizard create flow."""
    if timeout <= 0:
        raise typer.BadParameter("timeout must be greater than zero.")
    if not dry_run:
        try:
            payload = apply_scenario_wizard_create(
                config,
                output_dir,
                runtime_bundle,
                expected_wizard_version=wizard_version,
                force=force,
                python_executable=python_executable,
                timeout_seconds=timeout,
            )
        except ScenarioWizardError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        _write_json_to_output(plan_output, payload)
        if not payload["created"]:
            raise typer.Exit(code=1)
        return
    payload = build_scenario_wizard_create_plan(
        config,
        output_dir,
        runtime_bundle,
        expected_wizard_version=wizard_version,
        force=force,
        python_executable=python_executable,
    )
    _write_json_to_output(plan_output, payload)
    if not payload["ready"]:
        raise typer.Exit(code=1)


@scenario_wizard_app.command("package")
def package_scenario_wizard_scenario(
    scenario: Path = typer.Option(
        ...,
        "--scenario",
        help="Generated Scenario Wizard scenario directory to package.",
    ),
    python_executable: str = typer.Option(
        "python3.12",
        "--python",
        help="Python executable used when a scenario-local virtualenv must be created.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow packaging when target zip files already exist.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Preview by default; --apply runs local packaging.",
    ),
    timeout: float = typer.Option(
        300.0,
        "--timeout",
        help="Timeout in seconds for each local package subprocess.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for package plan or result JSON (defaults to stdout).",
    ),
) -> None:
    """Plan or run local packaging for a generated Scenario Wizard scenario."""
    if timeout <= 0:
        raise typer.BadParameter("timeout must be greater than zero.")
    if dry_run:
        payload = build_scenario_wizard_package_plan(
            scenario,
            force=force,
            python_executable=python_executable,
        )
        _write_json_to_output(output, payload)
        if not payload["ready"]:
            raise typer.Exit(code=1)
        return
    try:
        payload = apply_scenario_wizard_package(
            scenario,
            force=force,
            python_executable=python_executable,
            timeout_seconds=timeout,
        )
    except ScenarioWizardError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _write_json_to_output(output, payload)
    if not payload["packaged"]:
        raise typer.Exit(code=1)


@spec_app.command("list")
def list_operations(
    ctx: typer.Context,
    tag: str | None = typer.Option(None, help="Filter operations by tag."),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of results."),
    offset: int = typer.Option(0, "--offset", help="Offset into the results list."),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="Comma-separated fields: operation_id,method,path,summary,tags.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    ops = index.list_operations(tag=tag)
    selected_fields = normalize_spec_fields(
        fields, default=["operation_id", "method", "path", "tags"]
    )
    ops = slice_operations(ops, limit=limit, offset=offset)
    console.print(render_operations_table(ops, fields=selected_fields))


@spec_app.command("search")
@spec_app.command("find")
def search_operations(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search operationId, path, tags, or summary."),
    tag: str | None = typer.Option(None, help="Filter operations by tag."),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of results."),
    offset: int = typer.Option(0, "--offset", help="Offset into the results list."),
    fields: str | None = typer.Option(
        None,
        "--fields",
        help="Comma-separated fields: operation_id,method,path,summary,tags.",
    ),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    ops = index.search_operations(query, tag=tag)
    if not ops:
        console.print("[yellow]No operations matched the search query.[/yellow]")
        return
    selected_fields = normalize_spec_fields(
        fields, default=["operation_id", "method", "path", "summary", "tags"]
    )
    ops = slice_operations(ops, limit=limit, offset=offset)
    console.print(render_operations_table(ops, title="Search Results", fields=selected_fields))


@spec_app.command("show")
def show_operation(ctx: typer.Context, operation_id: str = typer.Argument(...)) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation(operation_id)
    table = Table(title=operation_id, box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Method", op.method.upper())
    table.add_row("Path", op.path)
    table.add_row("Summary", op.summary or "-")
    table.add_row("Tags", ", ".join(op.tags) or "-")
    table.add_row("Security", ", ".join(format_security(op.security)) or "-")
    if op.parameters:
        params_table = Table(title="Parameters", box=box.MINIMAL_DOUBLE_HEAD)
        params_table.add_column("Name")
        params_table.add_column("In")
        params_table.add_column("Required")
        params_table.add_column("Type")
        for param in op.parameters:
            schema = param.get("schema", {})
            params_table.add_row(
                param.get("name", ""),
                param.get("in", ""),
                "yes" if param.get("required") else "no",
                schema.get("type", ""),
            )
        console.print(params_table)
    console.print(table)


@app.command("call")
def call(
    ctx: typer.Context,
    operation_id: str = typer.Argument(..., help="operationId from the OpenAPI schema."),
    param: list[str] = typer.Option(
        [], "--param", "-p", help="key=value pairs for path/query parameters."
    ),
    header: list[str] = typer.Option([], "--header", "-H", help="Custom headers (key=value)."),
    cookie: list[str] = typer.Option([], "--cookie", help="Cookie parameters (key=value)."),
    body: str | None = typer.Option(None, help="JSON body string."),
    body_file: Path | None = typer.Option(
        None, exists=True, readable=True, help="Load JSON body from a file."
    ),
    form: list[str] = typer.Option([], "--form", help="Form fields (key=value)."),
    form_file: list[str] = typer.Option([], "--form-file", help="Form files (key=path)."),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        is_flag=True,
        help="Prompt for missing parameters or request bodies.",
    ),
    output: Path | None = typer.Option(None, help="Write response body to a file."),
    output_format: str | None = typer.Option(
        None,
        "--output-format",
        help="Response format: pretty-json | raw | csv.",
    ),
    base_url: str | None = typer.Option(None, help="Override base URL for this call."),
    timeout: float | None = typer.Option(None, help="Override request timeout."),
    log_json: bool | None = typer.Option(
        None, "--log-json/--no-log-json", help="Enable JSON structured logging."
    ),
    log_level: str | None = typer.Option(
        None,
        help=f"Logging level ({', '.join(sorted(LOG_LEVELS))}).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
    auth_scheme: str = typer.Option(
        "auto", help="auto | account-token | jwt | none (override auth resolution)."
    ),
    insecure: bool = typer.Option(
        False, "--insecure", help="Disable TLS verification (avoid unless necessary)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", is_flag=True, help="Show the request without sending it."
    ),
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
        params = parse_key_value_pairs(param, coerce=False)
        headers = parse_key_value_pairs(header, coerce=False)
        cookies = parse_key_value_pairs(cookie, coerce=False)
        body_payload = load_json_payload(body, body_file)
        form_fields = parse_key_value_pairs(form, coerce=False) if form else {}
        form_files, form_handles = parse_form_files(form_file) if form_file else ([], [])
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
        preview_headers.update(
            redact_headers(auth.build_headers(op))
        )
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


@export_app.command("templates")
def export_templates(
    ctx: typer.Context,
    output: Path = typer.Option(
        Path("assessment_templates.csv"),
        "--output",
        "-o",
        help="Destination file (.csv or .json).",
    ),
    file_format: str | None = typer.Option(
        None,
        "--format",
        help="Output format. Defaults to file extension or csv.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Page size for API pagination."),
    include_empty: bool = typer.Option(
        False,
        "--include-empty",
        help="Include templates with no scenarios (CSV only).",
    ),
    scenario_details: bool = typer.Option(
        False,
        "--scenario-details/--no-scenario-details",
        help="Fetch scenario names/types via per-ID lookups (slower, may skip failures).",
    ),
    scenario_details_lenient: bool = typer.Option(
        False,
        "--scenario-details-lenient/--scenario-details-strict",
        help="Continue if individual scenario lookups fail.",
    ),
    scenario_details_retries: int = typer.Option(
        0,
        "--scenario-details-retries",
        min=0,
        help="Retry attempts per scenario ID when --scenario-details-lenient is set.",
    ),
    scenario_concurrency: int = typer.Option(
        4,
        "--scenario-concurrency",
        min=1,
        help="Max concurrent per-ID scenario lookups when --scenario-details is set.",
    ),
    insecure: bool = typer.Option(
        False, "--insecure", help="Disable TLS verification for this export."
    ),
    timeout: float | None = typer.Option(
        None, "--timeout", help="Request timeout in seconds."
    ),
) -> None:
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)
    fmt = resolve_format(output, file_format)
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

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
    output: Path = typer.Option(
        Path("scenarios.csv"),
        "--output",
        "-o",
        help="Destination file (.csv or .json).",
    ),
    file_format: str | None = typer.Option(
        None,
        "--format",
        help="Output format. Defaults to file extension or csv.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Page size for API pagination."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)
    fmt = resolve_format(output, file_format)
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

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
    output: Path = typer.Option(
        Path("assessments.csv"),
        "--output",
        "-o",
        help="Destination file (.csv or .json).",
    ),
    file_format: str | None = typer.Option(
        None,
        "--format",
        help="Output format. Defaults to file extension or csv.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Page size for API pagination."),
    max_pages: int | None = typer.Option(
        None, "--max-pages", help="Maximum number of pages to fetch."
    ),
    asset_group_id: list[str] | None = typer.Option(
        None,
        "--asset-group-id",
        help="Filter by asset group IDs (repeat or comma-separated).",
    ),
    blueprint_id: str | None = typer.Option(None, "--blueprint-id", help="Filter by blueprint ID."),
    execution_strategy: int | None = typer.Option(
        None,
        "--execution-strategy",
        help="Execution strategy: 0=prevention+detection, 1=prevention.",
    ),
    has_default_schedule: bool | None = typer.Option(
        None,
        "--has-default-schedule/--no-has-default-schedule",
        help="Filter by default schedule usage.",
    ),
    name: str | None = typer.Option(None, "--name", help="Filter by exact assessment name."),
    report_instance_type: str | None = typer.Option(
        None, "--report-instance-type", help="Filter by report instance type."
    ),
    search: str | None = typer.Option(
        None, "--search", help="Filter by name/description search terms."
    ),
    use_scenario_alert_rules: bool | None = typer.Option(
        None,
        "--use-scenario-alert-rules/--no-use-scenario-alert-rules",
        help="Filter by scenario alert rules usage.",
    ),
    version: int | None = typer.Option(
        None,
        "--version",
        help="Filter by assessment version.",
    ),
    zones_ordering: list[str] | None = typer.Option(
        None,
        "--zones-ordering",
        help="Order by zone fields (repeat or comma-separated).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)
    fmt = resolve_format(output, file_format)
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
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
    output: Path = typer.Option(
        Path("tests.csv"),
        "--output",
        "-o",
        help="Destination file (.csv or .json).",
    ),
    file_format: str | None = typer.Option(
        None,
        "--format",
        help="Output format. Defaults to file extension or csv.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Page size for API pagination."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    cfg = load_config_or_exit()
    try:
        base_url = resolve_base_url(cfg, None)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    warn_if_insecure(base_url)
    fmt = resolve_format(output, file_format)
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc

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


@scenarios_app.command("list")
def list_scenarios(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for output (defaults to stdout).",
    ),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    order_by: str | None = typer.Option(None, "--order-by", help="Order by a specific field."),
    search: str | None = typer.Option(None, "--search", help="Scenario search query."),
    tag: str | None = typer.Option(None, "--tag", help="Scenario tag name or ID filter."),
    name: str | None = typer.Option(None, "--name", help="Exact scenario name to match."),
    modified_after: str | None = typer.Option(
        None,
        "--modified-after",
        help="Filter scenarios modified at or after this date-time (ISO 8601).",
    ),
    last_updated: str | None = typer.Option(
        None,
        "--last-updated",
        help="Deprecated alias for --modified-after.",
    ),
    mitre_platforms: str | None = typer.Option(
        None,
        "--mitre-platforms",
        help="Filter by MITRE platforms (API format).",
    ),
    hierarchy: str | None = typer.Option(None, "--hierarchy", help="Hierarchy filter."),
    object_fingerprint: str | None = typer.Option(
        None,
        "--object-fingerprint",
        help="Scenario object fingerprint.",
    ),
    parameters_description: str | None = typer.Option(
        None,
        "--parameters-description",
        help="Filter by parameters description.",
    ),
    scenario_template_instance: str | None = typer.Option(
        None,
        "--scenario-template-instance",
        help="Scenario template instance UUID filter.",
    ),
    api_backend: str = typer.Option(
        "native",
        "--api-backend",
        help="Experimental read-only API backend: native or platform-api.",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    scenario_id: str = typer.Argument(..., help="Scenario ID (UUID)."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for output (defaults to stdout for JSON).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    packages: list[Path] = typer.Argument(
        ...,
        help="Scenario Wizard package zip(s) to upload.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the upload. Without --apply, print a dry-run request plan.",
    ),
    endpoint: str = typer.Option(
        "/v1/scenario_templates",
        "--endpoint",
        help="Relative out-of-spec upload endpoint captured from the UI.",
    ),
    field_name: str = typer.Option(
        "zip_file",
        "--field-name",
        help="Multipart form field name for the scenario package.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON dry-run or upload responses.",
    ),
    raw_response: bool = typer.Option(
        False,
        "--raw-response",
        help="Include unredacted upload response bodies. Use only for trusted local output.",
    ),
    auth_scheme: str = typer.Option(
        "auto",
        "--auth-scheme",
        help="auto | account-token | jwt | none (override auth resolution).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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


@assessments_app.command("list")
def list_assessments(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    search: str | None = typer.Option(None, "--search", help="Filter by name/description terms."),
    name: str | None = typer.Option(None, "--name", help="Filter by exact assessment name."),
    asset_group_id: list[str] | None = typer.Option(
        None,
        "--asset-group-id",
        help="Filter by asset group id(s) (repeat or comma-separated).",
    ),
    blueprint_id: str | None = typer.Option(None, "--blueprint-id", help="Filter by blueprint id."),
    execution_strategy: int | None = typer.Option(
        None,
        "--execution-strategy",
        help="Filter by execution strategy (0=Prevention and Detection, 1=Prevention).",
    ),
    has_default_schedule: bool | None = typer.Option(
        None,
        "--has-default-schedule/--no-has-default-schedule",
        help="Filter by default schedule usage.",
    ),
    id_in: list[str] | None = typer.Option(
        None,
        "--id",
        "--id-in",
        help="Filter by assessment id(s) (repeat or comma-separated).",
    ),
    report_instance_type: str | None = typer.Option(
        None, "--report-instance-type", help="Filter by report instance type."
    ),
    tag_id: str | None = typer.Option(None, "--tag-id", help="Filter by tag ID."),
    tag_ids: list[str] | None = typer.Option(
        None,
        "--tag-ids",
        help="Filter by tag IDs (repeat or comma-separated).",
    ),
    use_scenario_alert_rules: bool | None = typer.Option(
        None,
        "--use-scenario-alert-rules/--no-use-scenario-alert-rules",
        help="Filter by scenario alert rules usage.",
    ),
    version: int | None = typer.Option(None, "--version", help="Filter by assessment version."),
    zones_ordering: list[str] | None = typer.Option(
        None,
        "--zones-ordering",
        help="Order by zone fields (repeat or comma-separated).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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

    # csv
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
    assessment_id: str = typer.Argument(..., help="Assessment UUID."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination file for JSON output (defaults to stdout)."
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    name: str = typer.Option(..., "--name", help="Assessment name."),
    scenario_id: list[str] = typer.Option(
        [], "--scenario-id", help="Scenario UUID to include (repeatable)."
    ),
    scenario_ids_file: Path | None = typer.Option(
        None,
        "--scenario-ids-file",
        exists=True,
        readable=True,
        help="Text file containing scenario UUIDs (one per line or comma-separated).",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    assessment_name = (name or "").strip()
    if not assessment_name:
        raise typer.BadParameter("--name is required.")

    requested: list[str] = []
    requested.extend([value for value in scenario_id if value and value.strip()])
    if scenario_ids_file is not None:
        requested.extend(_load_uuid_list_from_file(scenario_ids_file))
    requested = _stable_dedup([value.strip() for value in requested if value.strip()])
    if not requested:
        raise typer.BadParameter("At least one --scenario-id (or --scenario-ids-file) is required.")

    scenario_ids = [_normalize_uuid(value, label="scenario-id") for value in requested]
    body: dict[str, Any] = {"name": assessment_name, "scenario_ids": scenario_ids}
    operation = build_det_pipeline_create_assessment_operation()

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        json_body=body,
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
    template_id: str = typer.Option(..., "--template-id", help="Assessment template UUID."),
    name: str = typer.Option(..., "--name", help="Assessment name (project_name)."),
    blueprint_id: str | None = typer.Option(None, "--blueprint-id", help="Blueprint UUID."),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    operation = index.get_operation("v1_assessments_project_from_template_create")
    body: dict[str, Any] = {
        "template": _normalize_uuid(template_id, label="--template-id"),
        "project_name": (name or "").strip(),
    }
    if not body["project_name"]:
        raise typer.BadParameter("--name is required.")
    if blueprint_id is not None:
        body["blueprint"] = _normalize_uuid(blueprint_id, label="--blueprint-id")

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        index=index,
        json_body=body,
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
    assessment_id: str = typer.Argument(..., help="Assessment UUID."),
    asset_id: list[str] = typer.Option(
        [],
        "--asset-id",
        help="Asset UUID to set as an assessment default target (repeatable).",
    ),
    asset_ids_file: Path | None = typer.Option(
        None,
        "--asset-ids-file",
        exists=True,
        readable=True,
        help="Text file containing asset UUIDs (one per line or comma-separated).",
    ),
    asset_group_id: list[str] = typer.Option(
        [],
        "--asset-group-id",
        help="Asset group UUID to set as an assessment default target (repeatable).",
    ),
    asset_group_ids_file: Path | None = typer.Option(
        None,
        "--asset-group-ids-file",
        exists=True,
        readable=True,
        help="Text file containing asset group UUIDs (one per line or comma-separated).",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    requested_assets: list[str] = []
    requested_assets.extend([value for value in asset_id if value and value.strip()])
    if asset_ids_file is not None:
        requested_assets.extend(_load_uuid_list_from_file(asset_ids_file))
    assets = [
        _normalize_uuid(value, label="asset-id")
        for value in _stable_dedup([value.strip() for value in requested_assets if value.strip()])
    ]

    requested_groups: list[str] = []
    requested_groups.extend([value for value in asset_group_id if value and value.strip()])
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

    path_params = {"id": _normalize_uuid(assessment_id, label="assessment-id")}
    body: dict[str, str] = {}
    if assets:
        body["assets"] = ",".join(assets)
    if asset_groups:
        body["asset_groups"] = ",".join(asset_groups)

    index = SpecIndex.from_file(ctx.obj["spec_path"])
    operation = index.get_operation("v1_assessments_update_defaults_create")

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=path_params,
        json_body=body,
        apply_request=lambda context, effective_timeout: svc_update_assessment_defaults(
            context,
            assessment_id=path_params["id"],
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
    assessment_id: str = typer.Argument(..., help="Assessment UUID."),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    path_params = {"id": _normalize_uuid(assessment_id, label="assessment-id")}
    query_params: dict[str, Any] = {}

    index = SpecIndex.from_file(ctx.obj["spec_path"])
    operation = index.get_operation("v1_assessments_run_all_create")

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=path_params,
        query_params=query_params,
        apply_request=lambda context, effective_timeout: svc_run_assessment(
            context,
            assessment_id=path_params["id"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@tests_app.command("list")
def list_tests(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    name: str | None = typer.Option(None, "--name", help="Filter by exact test name."),
    project_template_test_id: str | None = typer.Option(
        None,
        "--project-template-test-id",
        help="Filter by project template test UUID.",
    ),
    run_in_hosted_agent_preferably: bool | None = typer.Option(
        None,
        "--run-in-hosted-agent-preferably/--no-run-in-hosted-agent-preferably",
        help="Filter by hosted-agent preference.",
    ),
    use_hosted_agent: bool | None = typer.Option(
        None,
        "--use-hosted-agent/--no-use-hosted-agent",
        help="Filter by use_hosted_agent.",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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

    filters = TestFilters(
        name=name,
        project_template_test_id=project_template_test_id,
        run_in_hosted_agent_preferably=run_in_hosted_agent_preferably,
        use_hosted_agent=use_hosted_agent,
    )
    query_params = build_test_query_params(filters)

    auth = build_auth_context(cfg, preferred_scheme="auto")
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    op = index.get_operation("v1_tests_list")
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
        items = svc_list_tests(
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

    # csv
    if output is None:
        raise typer.BadParameter("CSV output requires --output.")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = build_test_summary_records(items)
    write_csv_records(output, records, preferred_fields=TEST_FIELD_ORDER)


@tests_app.command("show")
def show_test(
    ctx: typer.Context,
    test_id: str = typer.Argument(..., help="Test UUID."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination file for JSON output (defaults to stdout)."
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_tests_retrieve")
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
        detail = fetch_test_detail(
            context,
            test_id=test_id,
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


def _normalize_required_path_id(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise typer.BadParameter(f"{label} is required.")
    return cleaned


def _build_validation_result_filters(
    *,
    days: int | None,
    project_ids: str | None,
    scope_id: str | None,
    tag_ids: str | None,
) -> ValidationResultFilters:
    if days is not None and days < 1:
        raise typer.BadParameter("days must be >= 1.")
    return ValidationResultFilters(
        days=days,
        project_ids=_normalize_optional_filter(project_ids),
        scope_id=_normalize_optional_filter(scope_id),
        tag_ids=_normalize_optional_filter(tag_ids),
    )


@results_app.command("list")
def list_results(
    ctx: typer.Context,
    mode: str = typer.Option(
        ResultsMode.SUMMARIES.value,
        "--mode",
        help="Result page type: summaries, phases, or logs.",
    ),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int = typer.Option(1, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    search: str | None = typer.Option(
        None,
        "--search",
        help="Search query for phases/logs modes.",
    ),
    tag_id: str | None = typer.Option(
        None,
        "--tag-id",
        help="Filter result summaries by tag ID.",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    result_summary_id: str | None = typer.Option(
        None,
        "--result-summary-id",
        help="Result summary ID to join phase results by.",
    ),
    scenario_job_id: str | None = typer.Option(
        None,
        "--scenario-job-id",
        help="Scenario job ID to join phase results by.",
    ),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int = typer.Option(1, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    result_summary_id: str | None = typer.Option(
        None,
        "--result-summary-id",
        help="Result summary ID to join phase logs by.",
    ),
    scenario_job_id: str | None = typer.Option(
        None,
        "--scenario-job-id",
        help="Scenario job ID to join phase logs by.",
    ),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int = typer.Option(1, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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


@validation_results_app.command("list")
def list_validation_results(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int = typer.Option(1, "--page", help="Page number within validation results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    days: int | None = typer.Option(None, "--days", help="Limit results to the last N days."),
    project_ids: str | None = typer.Option(
        None,
        "--project-ids",
        help="Comma-separated project/assessment IDs filter.",
    ),
    scope_id: str | None = typer.Option(None, "--scope-id", help="Scope ID filter."),
    tag_ids: str | None = typer.Option(None, "--tag-ids", help="Comma-separated tag IDs filter."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records, _has_next = svc_fetch_validation_results(
            context,
            by_asset=False,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@validation_results_app.command("by-asset")
def list_validation_results_by_asset(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int = typer.Option(1, "--page", help="Page number within validation results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    days: int | None = typer.Option(None, "--days", help="Limit results to the last N days."),
    project_ids: str | None = typer.Option(
        None,
        "--project-ids",
        help="Comma-separated project/assessment IDs filter.",
    ),
    scope_id: str | None = typer.Option(None, "--scope-id", help="Scope ID filter."),
    tag_ids: str | None = typer.Option(None, "--tag-ids", help="Comma-separated tag IDs filter."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    if page < 1:
        raise typer.BadParameter("page must be >= 1.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records, _has_next = svc_fetch_validation_results(
            context,
            by_asset=True,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@validation_results_app.command("asset-executions")
def list_validation_result_asset_executions(
    ctx: typer.Context,
    asset_id: str = typer.Argument(..., help="Asset ID."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    days: int | None = typer.Option(None, "--days", help="Limit results to the last N days."),
    project_ids: str | None = typer.Option(
        None,
        "--project-ids",
        help="Comma-separated project/assessment IDs filter.",
    ),
    scope_id: str | None = typer.Option(None, "--scope-id", help="Scope ID filter."),
    tag_ids: str | None = typer.Option(None, "--tag-ids", help="Comma-separated tag IDs filter."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )
    asset_id = _normalize_required_path_id(asset_id, label="asset_id")

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records = svc_fetch_validation_result_executions(
            context,
            asset_id=asset_id,
            scenario_id=None,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@validation_results_app.command("scenario-executions")
def list_validation_result_scenario_executions(
    ctx: typer.Context,
    scenario_id: str = typer.Argument(..., help="Scenario ID."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    days: int | None = typer.Option(None, "--days", help="Limit results to the last N days."),
    project_ids: str | None = typer.Option(
        None,
        "--project-ids",
        help="Comma-separated project/assessment IDs filter.",
    ),
    scope_id: str | None = typer.Option(None, "--scope-id", help="Scope ID filter."),
    tag_ids: str | None = typer.Option(None, "--tag-ids", help="Comma-separated tag IDs filter."),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    _validate_records_output_options(output_format, output)
    filters = _build_validation_result_filters(
        days=days,
        project_ids=project_ids,
        scope_id=scope_id,
        tag_ids=tag_ids,
    )
    scenario_id = _normalize_required_path_id(scenario_id, label="scenario_id")

    context, timeout = _prepare_read_only_context(ctx, insecure=insecure, timeout=timeout)
    try:
        records = svc_fetch_validation_result_executions(
            context,
            asset_id=None,
            scenario_id=scenario_id,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
        )
    except ValueError as exc:
        _handle_results_value_error(exc)
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc)

    _write_records_output(records=records, output_format=output_format, output=output)


@assets_app.command("list")
def list_assets(
    ctx: typer.Context,
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    search: str | None = typer.Option(None, "--search", help="Asset search query."),
    hostname: str | None = typer.Option(None, "--hostname", help="Filter by asset hostname."),
    ipv4_address: str | None = typer.Option(None, "--ipv4-address", help="Filter by IPv4 address."),
    ipv6_address: str | None = typer.Option(None, "--ipv6-address", help="Filter by IPv6 address."),
    deployment_state_id: int | None = typer.Option(
        None, "--deployment-state-id", help="Filter by deployment state number."
    ),
    deepsurface_last_seen_in_host_analysis_at: str | None = typer.Option(
        None,
        "--deepsurface-last-seen-in-host-analysis-at",
        help="Filter by DeepSurface last host-analysis timestamp.",
    ),
    deepsurface_sync_state: str | None = typer.Option(
        None,
        "--deepsurface-sync-state",
        help="Filter by DeepSurface sync state.",
    ),
    deepsurface_sync_state_changed_at: str | None = typer.Option(
        None,
        "--deepsurface-sync-state-changed-at",
        help="Filter by DeepSurface sync-state changed timestamp.",
    ),
    asset_group: str | None = typer.Option(
        None, "--asset-group", help="Filter by asset group UUID."
    ),
    activity_type: str | None = typer.Option(
        None, "--activity-type", help="Filter by DEVICE, DOMAIN, or TESTPOINT."
    ),
    ordering: str | None = typer.Option(None, "--ordering", help="Order by an asset field."),
    api_backend: str = typer.Option(
        "native",
        "--api-backend",
        help="Experimental read-only API backend: native or platform-api.",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    try:
        api_backend = normalize_api_backend(api_backend)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    filters = AssetFilters(
        search=search,
        hostname=hostname,
        ipv4_address=ipv4_address,
        ipv6_address=ipv6_address,
        deployment_state_id=deployment_state_id,
        deepsurface_last_seen_in_host_analysis_at=deepsurface_last_seen_in_host_analysis_at,
        deepsurface_sync_state=deepsurface_sync_state,
        deepsurface_sync_state_changed_at=deepsurface_sync_state_changed_at,
        asset_group=asset_group,
        activity_type=activity_type,
        ordering=ordering,
    )
    try:
        query_params = build_asset_query_params(filters)
    except ValueError as exc:
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
    op = index.get_operation("v1_assets_list")
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
        items = svc_list_assets(
            context,
            page=page,
            page_size=page_size,
            query_params=query_params or None,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
            api_backend=api_backend,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
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
    records = build_asset_summary_records(items)
    write_csv_records(output, records, preferred_fields=ASSET_FIELD_ORDER)


@assets_app.command("show")
def show_asset(
    ctx: typer.Context,
    asset_id: str = typer.Argument(..., help="Asset UUID."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination file for JSON output (defaults to stdout)."
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_assets_retrieve")
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
        detail = fetch_asset_detail(
            context,
            asset_id=asset_id,
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


@asset_groups_app.command("list")
def list_asset_groups(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", help="Asset group search query."),
    asset_group_id: str | None = typer.Option(
        None, "--id", "--asset-group-id", help="Filter by asset group UUID."
    ),
    name: str | None = typer.Option(None, "--name", help="Exact asset group name filter."),
    description: str | None = typer.Option(
        None, "--description", help="Asset group description filter."
    ),
    company: str | None = typer.Option(None, "--company", help="Filter by company UUID."),
    company_id: str | None = typer.Option(None, "--company-id", help="Filter by company UUID."),
    user: str | None = typer.Option(None, "--user", help="Filter by user UUID."),
    user_id: str | None = typer.Option(None, "--user-id", help="Filter by user UUID."),
    created: str | None = typer.Option(None, "--created", help="Filter by created timestamp."),
    created_after: str | None = typer.Option(
        None, "--created-after", help="Filter by created-after timestamp."
    ),
    modified: str | None = typer.Option(None, "--modified", help="Filter by modified timestamp."),
    ordering: str | None = typer.Option(None, "--ordering", help="Order by an asset group field."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_asset_groups_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    filters = AssetGroupFilters(
        search=search,
        asset_group_id=asset_group_id,
        name=name,
        description=description,
        company=company,
        company_id=company_id,
        user=user,
        user_id=user_id,
        created=created,
        created_after=created_after,
        modified=modified,
        ordering=ordering,
    )
    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        asset_groups = svc_list_asset_groups(
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
        records = build_asset_group_summary_records(asset_groups)
        write_csv_records(output, records, preferred_fields=ASSET_GROUP_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, asset_groups)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, asset_groups)


@asset_groups_app.command("show")
def show_asset_group(
    ctx: typer.Context,
    asset_group_id: str = typer.Argument(..., help="Asset group UUID."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination file for JSON output (defaults to stdout)."
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_asset_groups_retrieve")
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
        detail = fetch_asset_group_detail(
            context,
            asset_group_id=asset_group_id,
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


@blueprints_app.command("list")
def list_blueprints(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", help="Blueprint search query."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_blueprints_list")
    try:
        warnings = ensure_auth(op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            console.print(f"[red]{line}[/red]")
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    filters = BlueprintFilters(search=search)
    context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
    try:
        blueprints = svc_list_blueprints(
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
        records = build_blueprint_summary_records(blueprints)
        write_csv_records(output, records, preferred_fields=BLUEPRINT_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, blueprints)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, blueprints)


@integrations_app.command("list")
def list_integrations(
    ctx: typer.Context,
    alert_correlation_plan: str | None = typer.Option(
        None, "--alert-correlation-plan", help="Filter by alert correlation plan UUID."
    ),
    company_connector_manager_setup: str | None = typer.Option(
        None,
        "--company-connector-manager-setup",
        help="Filter by connector manager setup UUID.",
    ),
    company_connector_manager_setup_id: str | None = typer.Option(
        None,
        "--company-connector-manager-setup-id",
        help="Filter by connector manager setup UUID.",
    ),
    description: str | None = typer.Option(
        None, "--description", help="Filter by connector description."
    ),
    display_name: str | None = typer.Option(
        None, "--display-name", help="Filter by connector display name."
    ),
    implemented_mixins: str | None = typer.Option(
        None, "--implemented-mixins", help="Filter by implemented mixins."
    ),
    is_deleted: str | None = typer.Option(
        None, "--is-deleted", help="Filter by deleted state: true or false."
    ),
    mode: str | None = typer.Option(None, "--mode", help="Filter by Ad Hoc or Automatic mode."),
    mttd_timezone: str | None = typer.Option(
        None, "--mttd-timezone", help="Filter by MTTD timezone UUID."
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="Filter by connector status (ACTIVE, DISABLED, ERROR, PENDING, TESTING, "
        "TEST_FAILED, TRANSIENT).",
    ),
    ordering: str | None = typer.Option(
        None, "--ordering", help="Order by an integration connector field."
    ),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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

    is_deleted_filter: bool | None = None
    if is_deleted is not None:
        normalized_is_deleted = is_deleted.strip().lower()
        if normalized_is_deleted in {"1", "true", "yes"}:
            is_deleted_filter = True
        elif normalized_is_deleted in {"0", "false", "no"}:
            is_deleted_filter = False
        else:
            raise typer.BadParameter("is-deleted must be true or false.")

    filters = IntegrationConnectorFilters(
        alert_correlation_plan=alert_correlation_plan,
        company_connector_manager_setup=company_connector_manager_setup,
        company_connector_manager_setup_id=company_connector_manager_setup_id,
        description=description,
        display_name=display_name,
        implemented_mixins=implemented_mixins,
        is_deleted=is_deleted_filter,
        mode=mode,
        mttd_timezone=mttd_timezone,
        status=status,
        ordering=ordering,
    )
    try:
        # Validate enum-like filters before loading config so local input errors fail fast.
        build_integration_connector_query_params(filters)
    except ValueError as exc:
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
    op = index.get_operation("v1_company_connectors_list")
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
        connectors = svc_list_integration_connectors(
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

    records = build_integration_connector_summary_records(connectors)
    if fmt == "csv":
        if output is None:
            console.print("[red]CSV output requires --output.[/red]")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=INTEGRATION_CONNECTOR_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)


@source_types_app.command("list")
def list_source_types(
    ctx: typer.Context,
    company_id: str = typer.Option(
        ...,
        "--company-id",
        help="Company UUID required by the source-types endpoint.",
    ),
    connector_id: str = typer.Option(
        ...,
        "--connector-id",
        help="Global connector UUID to list source types for.",
    ),
    object_fingerprint: str | None = typer.Option(
        None,
        "--object-fingerprint",
        help="Filter by source type object fingerprint.",
    ),
    unassigned_for: str | None = typer.Option(
        None,
        "--unassigned-for",
        help="Assessment or object UUID used by the unassigned_for filter.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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

    filters = SourceTypeFilters(
        company_id=_normalize_uuid(company_id, label="--company-id"),
        connector_id=_normalize_uuid(connector_id, label="--connector-id"),
        object_fingerprint=object_fingerprint,
        unassigned_for=(
            _normalize_uuid(unassigned_for, label="--unassigned-for")
            if unassigned_for is not None
            else None
        ),
    )

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
    op = index.get_operation("v1_source_types_list")
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
        source_types = svc_list_source_types(
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

    records = build_source_type_summary_records(source_types)
    if fmt == "csv":
        if output is None:
            console.print("[red]CSV output requires --output.[/red]")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=SOURCE_TYPE_FIELD_ORDER)
        return

    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)


@tests_app.command("create")
def create_test(
    ctx: typer.Context,
    assessment_id: str = typer.Option(..., "--assessment-id", help="Assessment UUID."),
    name: str = typer.Option(..., "--name", help="Test name."),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    test_name = (name or "").strip()
    if not test_name:
        raise typer.BadParameter("--name is required.")
    body = {
        "project": _normalize_uuid(assessment_id, label="--assessment-id"),
        "name": test_name,
    }
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    operation = index.get_operation("v1_tests_create")

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        index=index,
        json_body=body,
        apply_request=lambda context, effective_timeout: svc_create_test(
            context,
            assessment_id=body["project"],
            name=body["name"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@tests_app.command("add-scenarios")
def add_test_scenarios(
    ctx: typer.Context,
    test_id: str = typer.Argument(..., help="Test UUID."),
    scenario_id: list[str] = typer.Option(
        [], "--scenario-id", help="Scenario UUID to include (repeatable)."
    ),
    scenario_ids_file: Path | None = typer.Option(
        None,
        "--scenario-ids-file",
        exists=True,
        readable=True,
        help="Text file containing scenario UUIDs (one per line or comma-separated).",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    requested: list[str] = []
    requested.extend([value for value in scenario_id if value and value.strip()])
    if scenario_ids_file is not None:
        requested.extend(_load_uuid_list_from_file(scenario_ids_file))
    requested = _stable_dedup([value.strip() for value in requested if value.strip()])
    if not requested:
        raise typer.BadParameter("At least one --scenario-id (or --scenario-ids-file) is required.")

    path_params = {"id": _normalize_uuid(test_id, label="test-id")}
    body = {"include": [_normalize_uuid(value, label="scenario-id") for value in requested]}
    index = SpecIndex.from_file(ctx.obj["spec_path"])
    operation = index.get_operation("v1_tests_bulk_add_scenarios_create")

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=path_params,
        json_body=body,
        apply_request=lambda context, effective_timeout: svc_add_scenarios_to_test(
            context,
            test_id=path_params["id"],
            scenario_ids=body["include"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@tests_app.command("get-status")
def get_test_status(
    ctx: typer.Context,
    test_id: str = typer.Argument(..., help="Test UUID."),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the network request (default is dry-run).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write API response JSON to a file (otherwise stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    path_params = {"id": _normalize_uuid(test_id, label="test-id")}
    query_params: dict[str, Any] = {}

    index = SpecIndex.from_file(ctx.obj["spec_path"])
    operation = index.get_operation("v1_tests_get_status_retrieve")

    _run_mutation_command(
        ctx,
        apply=apply,
        operation=operation,
        output=output,
        timeout=timeout,
        index=index,
        path_params=path_params,
        query_params=query_params,
        apply_request=lambda context, effective_timeout: svc_get_test_status(
            context,
            test_id=path_params["id"],
            insecure=insecure,
            timeout=effective_timeout,
            check_auth=False,
        ),
    )


@templates_app.command("list")
def list_templates(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", help="Assessment template search query."),
    template_name: str | None = typer.Option(
        None, "--template-name", help="Exact assessment template name filter."
    ),
    project_name: str | None = typer.Option(
        None, "--project-name", help="Exact generated project name filter."
    ),
    category: str | None = typer.Option(None, "--category", help="Assessment template category."),
    assessment_type: str | None = typer.Option(
        None, "--assessment-type", help="Assessment template type filter."
    ),
    behavior: str | None = typer.Option(None, "--behavior", help="Behavior filter."),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    template_id: str = typer.Argument(..., help="Assessment template UUID."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination file for JSON output (defaults to stdout)."
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    template_id: str | None = typer.Option(
        None,
        "--template-id",
        "--project-template-id",
        help="Filter by assessment template UUID.",
    ),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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


@tags_app.command("list")
def list_tags(
    ctx: typer.Context,
    search: str | None = typer.Option(None, "--search", help="Tag search query."),
    name: str | None = typer.Option(None, "--name", help="Exact tag name filter."),
    display_name: str | None = typer.Option(
        None, "--display-name", help="Exact tag display name filter."
    ),
    content_type: str | None = typer.Option(None, "--content-type", help="Content type filter."),
    exclude_tags_by_tag_set: str | None = typer.Option(
        None, "--exclude-tag-set", help="Exclude tags by tag set UUID."
    ),
    object_fingerprint: str | None = typer.Option(
        None, "--object-fingerprint", help="Object fingerprint filter."
    ),
    page_size: int = typer.Option(200, "--page-size", help="Number of results per page."),
    page: int | None = typer.Option(None, "--page", help="Page number within results."),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Output format: json or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for JSON output (defaults to stdout).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    if exclude_tags_by_tag_set:
        try:
            uuid.UUID(exclude_tags_by_tag_set)
        except ValueError as exc:
            raise typer.BadParameter("exclude-tag-set must be a valid UUID.") from exc

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
    tags_op = index.get_operation("v1_tags_list")
    try:
        warnings = ensure_auth(tags_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        typer.secho(warning, err=True, fg=typer.colors.YELLOW)

    filters = TagFilters(
        search=search,
        name=name,
        display_name=display_name,
        content_type=content_type,
        exclude_tags_by_tag_set=exclude_tags_by_tag_set,
        object_fingerprint=object_fingerprint,
    )

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        tags = svc_list_tags(
            context,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc, use_typer=True)

    records = build_tag_summary_records(tags)

    if fmt == "csv":
        if output is None:
            typer.secho("CSV output requires --output.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, records, preferred_fields=("id", "name", "display_name"))
        return
    if output is None:
        write_json(sys.stdout, records)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, records)


@tags_app.command("show")
def show_tag(
    ctx: typer.Context,
    tag_id: str = typer.Argument(..., help="Tag UUID."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Destination file for JSON output (defaults to stdout)."
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
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
    op = index.get_operation("v1_tags_retrieve")
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
        detail = fetch_tag_detail(
            context,
            tag_id=tag_id,
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


@tags_app.command("search")
def search_tags(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search term for tags."),
    limit: int = typer.Option(20, "--limit", help="Maximum number of tags to return."),
    output_format: str = typer.Option(
        "table",
        "--output-format",
        help="Output format: table, json, or csv.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination file for output (CSV requires --output).",
    ),
    insecure: bool = typer.Option(False, "--insecure", help="Disable TLS verification."),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
) -> None:
    search_term = query.strip()
    if not search_term:
        raise typer.BadParameter("query must be non-empty.")
    if limit < 1:
        raise typer.BadParameter("limit must be >= 1.")
    fmt = output_format.lower()
    if fmt not in {"table", "json", "csv"}:
        raise typer.BadParameter("output-format must be table, json, or csv.")
    if fmt == "csv" and output is None:
        typer.secho("CSV output requires --output.")
        raise typer.Exit(code=1)
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
    tags_op = index.get_operation("v1_tags_list")
    try:
        warnings = ensure_auth(tags_op, auth)
    except ValueError as exc:
        for line in str(exc).splitlines():
            typer.secho(line, err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for warning in warnings:
        typer.secho(warning, err=True, fg=typer.colors.YELLOW)

    try:
        context = ServiceContext(config=cfg, base_url=base_url, auth=auth, spec=index)
        records = svc_search_tags(
            context,
            query=search_term,
            limit=limit,
            insecure=insecure,
            timeout=timeout,
            check_auth=False,
        )
    except httpx.HTTPError as exc:
        _print_http_error_and_exit(exc, use_typer=True)

    payload = build_tag_summary_records(records)

    if fmt == "csv":
        if output is None:
            typer.secho("CSV output requires --output.")
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_csv_records(output, payload, preferred_fields=("id", "name", "display_name"))
        return
    if fmt == "json":
        if output is None:
            write_json(sys.stdout, payload)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, payload)
        return

    table = Table(title=f"Tags matching '{search_term}'", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Display Name")
    for tag in payload:
        table.add_row(
            str(tag.get("id") or ""),
            str(tag.get("name") or ""),
            str(tag.get("display_name") or ""),
        )
    console.print(table)


@app.command("join", help="Join AttackIQ exports with GitLab issues.")
def join_exports(
    mode: str = typer.Argument(
        "datasets",
        help="Join mode: datasets (default) or det-pipeline.",
    ),
    assessments: Path | None = typer.Option(
        None,
        "--assessments",
        exists=True,
        readable=True,
        help="Path to assessments CSV export.",
    ),
    scenarios: Path | None = typer.Option(
        None,
        "--scenarios",
        exists=True,
        readable=True,
        help="Path to scenarios CSV export.",
    ),
    issues: Path | None = typer.Option(
        None,
        "--issues",
        exists=True,
        readable=True,
        help="Path to GitLab issues CSV export.",
    ),
    outdir: Path | None = typer.Option(
        None,
        "--outdir",
        help="Output directory for joined CSVs and manifest.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="GitLab project_id for det-pipeline apply mode.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply network changes (GitLab updates + AttackIQ assessment creation).",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run mode (default true).",
    ),
    top_k: int = typer.Option(5, "--top-k", help="Max scenario recommendations per issue."),
    top_n_per_issue: int = typer.Option(
        1,
        "--top-n-per-issue",
        help="Top N scenario ids per issue for DET assessment planning.",
    ),
    force_tool_label: bool = typer.Option(
        False,
        "--force-tool-label",
        help="Allow tool label updates in patch plan.",
    ),
    allow_append_sections: bool = typer.Option(
        False,
        "--allow-append-sections",
        help="Append Detection Mapping section when missing.",
    ),
    timestamp: str | None = typer.Option(
        None,
        "--timestamp",
        help="Override created_utc in manifest (UTC ISO8601, e.g. 2026-01-26T00:00:00Z).",
    ),
    fail_on_missing_scenario: bool = typer.Option(
        True,
        "--fail-on-missing-scenario/--no-fail-on-missing-scenario",
        help="Fail when an assessment references a missing scenario.",
    ),
    fail_on_malformed_scenario_technique: bool = typer.Option(
        True,
        "--fail-on-malformed-scenario-technique/--no-fail-on-malformed-scenario-technique",
        help="Fail when a scenario technique is malformed.",
    ),
) -> None:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "det-pipeline":
        if issues is None:
            raise typer.BadParameter("--issues is required for det-pipeline mode.")
        if scenarios is None:
            raise typer.BadParameter("--scenarios is required for det-pipeline mode.")
        if outdir is None:
            raise typer.BadParameter("--outdir is required for det-pipeline mode.")
        if project_id is None:
            raise typer.BadParameter("--project-id is required for det-pipeline mode.")
        det_options = joiner_cli.DetPipelineOptions(
            issues=issues,
            scenarios=scenarios,
            outdir=outdir,
            project_id=project_id,
            apply=apply,
            dry_run=(dry_run and not apply),
            top_k=top_k,
            top_n_per_issue=top_n_per_issue,
            force_tool_label=force_tool_label,
            allow_append_sections=allow_append_sections,
            timestamp=timestamp,
        )
        joiner_cli.run_det_pipeline(det_options)
        return
    if normalized_mode != "datasets":
        raise typer.BadParameter("mode must be either 'datasets' or 'det-pipeline'.")
    if assessments is None:
        raise typer.BadParameter("--assessments is required for datasets mode.")
    if scenarios is None:
        raise typer.BadParameter("--scenarios is required for datasets mode.")
    if issues is None:
        raise typer.BadParameter("--issues is required for datasets mode.")
    if outdir is None:
        raise typer.BadParameter("--outdir is required for datasets mode.")
    join_options = joiner_cli.JoinOptions(
        assessments=assessments,
        scenarios=scenarios,
        issues=issues,
        outdir=outdir,
        timestamp=timestamp,
        fail_on_missing_scenario=fail_on_missing_scenario,
        fail_on_malformed_scenario_technique=fail_on_malformed_scenario_technique,
    )
    joiner_cli.run_join(join_options)


@app.command("tui")
def tui(
    ctx: typer.Context,
    page_size: int = typer.Option(20, "--page-size", help="Scenarios page size."),
    order_by: str | None = typer.Option(
        "last_updated",
        "--order-by",
        help="Scenario order_by value (per API support).",
    ),
    search: str | None = typer.Option(None, "--search", help="Scenario search query."),
    tag: str | None = typer.Option(None, "--tag", help="Scenario tag name or ID filter."),
    filter_debounce: float = typer.Option(
        0.4,
        "--filter-debounce",
        help="Filter debounce in seconds (min 0.1).",
    ),
    timeout: float | None = typer.Option(None, "--timeout", help="Request timeout in seconds."),
    auth_scheme: str = typer.Option(
        "auto", help="auto | account-token | jwt | none (override auth resolution)."
    ),
    insecure: bool = typer.Option(
        False, "--insecure", help="Disable TLS verification (avoid unless necessary)."
    ),
) -> None:
    scheme_normalized = auth_scheme.lower()
    if scheme_normalized not in {"auto", "account-token", "jwt", "none"}:
        raise typer.BadParameter("auth-scheme must be one of: auto, account-token, jwt, none.")
    if page_size < 1:
        raise typer.BadParameter("page-size must be >= 1.")
    if timeout is not None:
        try:
            timeout = validate_timeout(timeout)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc
    if filter_debounce < 0.1:
        raise typer.BadParameter("filter-debounce must be >= 0.1.")
    if insecure:
        console.print("[yellow]Warning: TLS verification disabled for this session.[/yellow]")
    if order_by and not order_by.strip():
        order_by = None
    if search and not search.strip():
        search = None
    if tag and not tag.strip():
        tag = None
    from attackiq_cli.tui import run_tui

    run_tui(
        spec_path=ctx.obj["spec_path"],
        page_size=page_size,
        order_by=order_by,
        search=search,
        tag=tag,
        filter_debounce=filter_debounce,
        insecure=insecure,
        timeout=timeout,
        auth_scheme=scheme_normalized,
    )


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


def format_security(entries: list[dict]) -> list[str]:
    names: list[str] = []
    for entry in entries or []:
        names.extend(entry.keys())
    return names


def validate_header_values(headers: dict[str, str]) -> None:
    for name, value in headers.items():
        if "\r" in value or "\n" in value:
            raise typer.BadParameter(
                f"Invalid value for header '{name}': control characters are not allowed."
            )


def mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if len(secret) <= 4:
        return "***"
    return f"{secret[:2]}***{secret[-2:]}"


def app_main() -> None:  # pragma: no cover - console entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    app_main()
