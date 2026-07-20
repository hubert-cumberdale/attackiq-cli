from __future__ import annotations

import csv
import json
from pathlib import Path

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_exports


def test_build_tui_export_path_formats_paged_and_unpaged_names(tmp_path: Path) -> None:
    assert tui_exports.build_tui_export_path(
        str(tmp_path),
        "scenarios",
        "json",
        page=2,
        timestamp="20260716T120000Z",
    ) == tmp_path / "exports" / "scenarios_page2_20260716T120000Z.json"
    assert tui_exports.build_tui_export_path(
        str(tmp_path),
        "settings",
        "csv",
        timestamp="20260716T120000Z",
    ) == tmp_path / "exports" / "settings_20260716T120000Z.csv"


def test_write_tui_export_writes_json_and_creates_parent(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "records.json"

    tui_exports.write_tui_export(output, "json", [{"name": "alpha", "count": 2}])

    assert json.loads(output.read_text(encoding="utf-8")) == [{"count": 2, "name": "alpha"}]


def test_write_tui_export_writes_preferred_csv_fields(tmp_path: Path) -> None:
    output = tmp_path / "records.csv"

    tui_exports.write_tui_export(
        output,
        "csv",
        [{"id": "one", "name": "Alpha", "extra": "ignored"}],
        preferred_fields=["id", "name", "missing"],
        include_preferred_missing=True,
        include_other_fields=False,
    )

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows == [["id", "name", "missing"], ["one", "Alpha", ""]]


def test_tui_module_reexports_utc_timestamp_for_compatibility() -> None:
    assert tui_module._utc_timestamp is tui_exports._utc_timestamp
