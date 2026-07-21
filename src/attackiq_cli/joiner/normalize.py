"""Normalization helpers for deterministic joiner output."""

from __future__ import annotations

from collections.abc import Iterable


def stable_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def list_to_string(items: Iterable[str], delimiter: str) -> str:
    return delimiter.join(items)

