from __future__ import annotations

import pytest

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_filters
from attackiq_cli.tui_provider import ResultsViewMode


def test_structured_filter_splits_commas_between_known_keys_only() -> None:
    parsed = tui_filters._parse_structured_filter(
        "q=alpha,beta,sort=name",
        keys={"query", "sort"},
        aliases={"q": "query"},
    )

    assert parsed == {"query": "alpha,beta", "sort": "name"}


def test_typed_filter_parsers_preserve_existing_errors() -> None:
    assert tui_filters._parse_filter_list("a, b,,c") == ["a", "b", "c"]
    assert tui_filters._parse_filter_int("42") == 42
    assert tui_filters._parse_filter_bool("yes") is True
    assert tui_filters._parse_filter_bool("off") is False

    with pytest.raises(ValueError, match="integer filters"):
        tui_filters._parse_filter_int("not-an-int")

    with pytest.raises(ValueError, match="boolean filters"):
        tui_filters._parse_filter_bool("sometimes")


def test_results_sort_resolution_uses_mode_specific_aliases() -> None:
    assert tui_filters._resolve_results_sort(
        ResultsViewMode.SUMMARIES,
        "status",
        "desc",
    ) == ("outcome", True)
    assert tui_filters._resolve_results_sort(
        ResultsViewMode.PHASES,
        "items",
        "reverse",
    ) == ("count", True)


def test_tui_module_reexports_filter_helpers_for_compatibility() -> None:
    assert tui_module._parse_scenario_filter is tui_filters._parse_scenario_filter
    assert tui_module._parse_results_filter is tui_filters._parse_results_filter
