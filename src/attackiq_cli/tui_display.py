from __future__ import annotations

from collections import Counter

import httpx

from attackiq_cli.tui_domains import CommandPaletteEntry


def _tab_shortcuts_text(*, include_export: bool) -> str:
    base = (
        "Keys: Ctrl+K=Commands [=Prev tab ]=Next tab n=Next p=Prev r=Refresh Enter=Apply filter "
        "Tab=Focus next q=Quit ?/h=Help Esc=Close help"
    )
    if include_export:
        return f"{base} e=Export JSON c=Export CSV"
    return base


def _palette_entry_matches(entry: CommandPaletteEntry, query: str) -> bool:
    if not query:
        return True
    tokens = [token for token in query.split() if token]
    searchable = " ".join(
        [
            entry.command_id.lower(),
            entry.label.lower(),
            entry.group.lower(),
            " ".join(keyword.lower() for keyword in entry.keywords),
            (entry.shortcut or "").lower(),
        ]
    )
    return all(token in searchable for token in tokens)


def _palette_group_hint(entries: list[CommandPaletteEntry]) -> str:
    if not entries:
        return "No matches"
    counts = Counter(entry.group for entry in entries)
    ordered_groups = list(dict.fromkeys(entry.group for entry in entries))
    return ", ".join(f"{group} {counts[group]}" for group in ordered_groups)


def _format_runtime_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ConnectError):
        return f"network connection failed ({exc})"
    if isinstance(exc, httpx.TimeoutException):
        return f"request timed out ({exc})"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"request failed ({exc.response.status_code})"
    if isinstance(exc, httpx.RequestError):
        return f"request failed ({exc})"
    return str(exc)
