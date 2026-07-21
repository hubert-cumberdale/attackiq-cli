from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from attackiq_cli.catalog import (
    CATALOG_CSV_FIELDS,
    DEFAULT_CATALOG_PATH,
    VALID_PROVIDERS,
    VALID_SCENARIO_STATUS,
    VALID_SURFACE,
    BasCatalog,
    CatalogError,
    build_catalog_coverage_summary,
    catalog_records_for_csv,
    filter_catalog_records,
    load_bas_catalog,
    normalize_catalog_records,
    validate_bas_catalog,
)
from attackiq_cli.exporter import write_csv_records
from attackiq_cli.mutations import write_json_payload

console = Console()

catalog_app = typer.Typer(
    help="Inspect local BAS scenario catalogs.",
    pretty_exceptions_show_locals=False,
)

__all__ = [
    "catalog_app",
    "list_catalog_records",
    "summarize_catalog_coverage",
    "validate_catalog",
]


def _write_json_to_output(output: Path | None, payload: Any) -> None:
    write_json_payload(
        output,
        payload,
        on_file_written=lambda path: console.print(f"Response written to {path}"),
    )


def _load_bas_catalog_or_exit(path: Path) -> BasCatalog:
    try:
        return load_bas_catalog(path)
    except (CatalogError, OSError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@catalog_app.command("validate")
def validate_catalog(
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            "-p",
            help="BAS catalog root containing a scenarios directory.",
        ),
    ] = DEFAULT_CATALOG_PATH,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for validation JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Validate a local BAS catalog without network access."""
    catalog = _load_bas_catalog_or_exit(path)
    payload = validate_bas_catalog(catalog)
    _write_json_to_output(output, payload)
    if not payload["valid"]:
        raise typer.Exit(code=1)


@catalog_app.command("list")
def list_catalog_records(
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            "-p",
            help="BAS catalog root containing a scenarios directory.",
        ),
    ] = DEFAULT_CATALOG_PATH,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Filter by provider: aws|azure."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            help="Filter by source catalog status: proposed|validated|lab_only.",
        ),
    ] = None,
    technique: Annotated[
        str | None,
        typer.Option("--technique", help="Filter by ATT&CK ID."),
    ] = None,
    surface: Annotated[
        str | None,
        typer.Option("--surface", help="Filter by surface such as IAM."),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", help="Case-insensitive text search."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Maximum number of records to return."),
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
            help="Destination file for output (CSV requires --output).",
        ),
    ] = None,
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
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            "-p",
            help="BAS catalog root containing a scenarios directory.",
        ),
    ] = DEFAULT_CATALOG_PATH,
    include_techniques: Annotated[
        bool,
        typer.Option(
            "--include-techniques",
            help="Include per-technique scenario detail in the JSON output.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for coverage JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Summarize coverage for a local BAS catalog."""
    catalog = _load_bas_catalog_or_exit(path)
    payload = build_catalog_coverage_summary(catalog)
    if not include_techniques:
        payload = dict(payload)
        payload.pop("techniques", None)
    _write_json_to_output(output, payload)
