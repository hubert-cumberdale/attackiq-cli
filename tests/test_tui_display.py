from __future__ import annotations

import httpx

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_display
from attackiq_cli.tui_domains import CommandPaletteEntry


def test_tab_shortcuts_text_includes_export_keys_only_when_requested() -> None:
    without_export = tui_display._tab_shortcuts_text(include_export=False)
    with_export = tui_display._tab_shortcuts_text(include_export=True)

    assert "Ctrl+K=Commands" in without_export
    assert "e=Export JSON" not in without_export
    assert "e=Export JSON c=Export CSV" in with_export


def test_palette_entry_matches_command_label_group_keywords_and_shortcut() -> None:
    entry = CommandPaletteEntry(
        command_id="cache:stats",
        label="Show TUI cache stats",
        group="Data",
        shortcut="-",
        keywords=("diagnostics", "counts"),
    )

    assert tui_display._palette_entry_matches(entry, "cache data")
    assert tui_display._palette_entry_matches(entry, "diagnostics")
    assert tui_display._palette_entry_matches(entry, "-")
    assert not tui_display._palette_entry_matches(entry, "export")


def test_palette_group_hint_counts_groups_in_entry_order() -> None:
    entries = [
        CommandPaletteEntry("switch:status", "Status", "Tabs"),
        CommandPaletteEntry("refresh", "Refresh", "Data"),
        CommandPaletteEntry("cache:stats", "Cache stats", "Data"),
    ]

    assert tui_display._palette_group_hint(entries) == "Tabs 1, Data 2"
    assert tui_display._palette_group_hint([]) == "No matches"


def test_format_runtime_error_preserves_existing_categories() -> None:
    request = httpx.Request("GET", "https://api.example.com/v1/scenarios")
    connect = httpx.ConnectError("dns failure", request=request)
    timeout = httpx.ReadTimeout("slow", request=request)
    response = httpx.Response(503, request=request)
    status = httpx.HTTPStatusError("unavailable", request=request, response=response)

    assert tui_display._format_runtime_error(connect).startswith("network connection failed")
    assert tui_display._format_runtime_error(timeout).startswith("request timed out")
    assert tui_display._format_runtime_error(status) == "request failed (503)"


def test_tui_module_reexports_display_helpers_for_compatibility() -> None:
    assert tui_module._tab_shortcuts_text is tui_display._tab_shortcuts_text
    assert tui_module._palette_entry_matches is tui_display._palette_entry_matches
    assert tui_module._format_runtime_error is tui_display._format_runtime_error
