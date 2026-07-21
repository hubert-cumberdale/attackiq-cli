from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from attackiq_cli.exporter import write_csv_records, write_json


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_tui_export_path(
    workspace_full: str,
    stem: str,
    fmt: str,
    *,
    page: int | None = None,
    timestamp: str | None = None,
) -> Path:
    timestamp_value = timestamp or _utc_timestamp()
    page_part = f"_page{page}" if page is not None else ""
    name = f"{stem}{page_part}_{timestamp_value}.{fmt}"
    return Path(workspace_full) / "exports" / name


def write_tui_export(
    output: Path,
    fmt: str,
    records: list[dict[str, Any]],
    *,
    preferred_fields: Iterable[str] | None = None,
    include_preferred_missing: bool = False,
    include_other_fields: bool = True,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        write_json(output, records)
        return
    write_csv_records(
        output,
        records,
        preferred_fields=preferred_fields,
        include_preferred_missing=include_preferred_missing,
        include_other_fields=include_other_fields,
    )
