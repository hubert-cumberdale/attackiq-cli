from __future__ import annotations

from attackiq_cli.tui_domains import (
    READ_ONLY_COMMAND_IDS,
    READ_ONLY_PREVIEW_COMMAND_IDS,
    TUI_DOMAIN_CONTROLLERS,
    allowed_command_ids_for_tab,
    build_command_palette_entries,
    filter_help_for_tab,
    focus_prefix_for_tab,
    tab_id_for_short_name,
)


def test_tui_domain_registry_builds_switch_palette_entries() -> None:
    entries = build_command_palette_entries()
    switch_entries = [entry for entry in entries if entry.command_id.startswith("switch:")]

    assert [entry.command_id for entry in switch_entries] == [
        "switch:status",
        "switch:scenarios",
        "switch:assessments",
        "switch:tests",
        "switch:assets",
        "switch:results",
        "switch:settings",
    ]
    assert [entry.label for entry in switch_entries] == [
        "Switch tab: Landing / Status",
        "Switch tab: Scenarios",
        "Switch tab: Assessments",
        "Switch tab: Tests",
        "Switch tab: Assets",
        "Switch tab: Results",
        "Switch tab: Settings",
    ]
    assert tab_id_for_short_name("results") == "tab_results"
    assert tab_id_for_short_name("unknown") is None


def test_tui_domain_command_availability_is_tab_scoped() -> None:
    switch_ids = {f"switch:{domain.key}" for domain in TUI_DOMAIN_CONTROLLERS}
    base_ids = switch_ids | {"help", "cache:clear", "cache:stats"}

    assert allowed_command_ids_for_tab("tab_status") == base_ids | {
        "export:csv",
        "export:json",
        "filter-help",
        "refresh",
    }

    list_tab_ids = {
        "tab_scenarios",
        "tab_results",
        "tab_assessments",
        "tab_tests",
        "tab_assets",
        "tab_settings",
    }
    expected_list_ids = base_ids | {
        "export:csv",
        "export:json",
        "filter-help",
        "focus:filter",
        "focus:search",
        "page:next",
        "page:prev",
        "refresh",
    }
    for tab_id in list_tab_ids:
        expected = set(expected_list_ids)
        if tab_id == "tab_scenarios":
            expected.add("preview:new-assessment")
        if tab_id == "tab_assessments":
            expected.update(
                {
                    "preview:assessment-defaults",
                    "preview:assessment-from-template",
                    "preview:assessment-run",
                    "preview:new-test",
                }
            )
        if tab_id == "tab_tests":
            expected.update({"preview:test-scenarios", "preview:test-status"})
        assert allowed_command_ids_for_tab(tab_id) == expected

    assert allowed_command_ids_for_tab("tab_unknown") == base_ids


def test_tui_domain_commands_remain_read_only() -> None:
    command_ids = {entry.command_id for entry in build_command_palette_entries()}
    forbidden_terms = ("apply", "create", "delete", "mutate", "mutation", "run", "update")

    assert {
        "preview:assessment-defaults",
        "preview:assessment-from-template",
        "preview:assessment-run",
        "preview:new-assessment",
        "preview:new-test",
        "preview:test-scenarios",
        "preview:test-status",
    } == READ_ONLY_PREVIEW_COMMAND_IDS
    assert command_ids <= READ_ONLY_COMMAND_IDS
    for entry in build_command_palette_entries():
        searchable = " ".join((entry.command_id, entry.label, *entry.keywords)).lower()
        if entry.command_id in READ_ONLY_PREVIEW_COMMAND_IDS:
            assert entry.command_id.startswith("preview:")
            assert not any(
                term in searchable
                for term in ("apply", "create", "delete", "mutate", "mutation", "update")
            )
            continue
        assert not any(term in searchable for term in forbidden_terms)


def test_tui_domain_filter_help_and_focus_prefixes() -> None:
    status_help = filter_help_for_tab("tab_status")
    scenario_help = filter_help_for_tab("tab_scenarios")
    results_help = filter_help_for_tab("tab_results")

    assert status_help is not None
    assert scenario_help is not None
    assert results_help is not None
    assert "Status tab has no list filters" in status_help
    assert "Scenario filters:" in scenario_help
    assert "Results filters:" in results_help
    assert filter_help_for_tab("tab_unknown") is None

    assert focus_prefix_for_tab("tab_status") is None
    assert focus_prefix_for_tab("tab_scenarios") == "scenarios"
    assert focus_prefix_for_tab("tab_results") == "results"
    assert focus_prefix_for_tab("tab_settings") == "settings"
    assert focus_prefix_for_tab("tab_unknown") is None
