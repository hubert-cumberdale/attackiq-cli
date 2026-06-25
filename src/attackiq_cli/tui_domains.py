from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandPaletteEntry:
    command_id: str
    label: str
    group: str
    shortcut: str | None = None
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class TuiDomainController:
    key: str
    tab_id: str
    label: str
    switch_keywords: tuple[str, ...]
    supports_refresh: bool
    supports_paging: bool = False
    supports_export: bool = False
    supports_focus: bool = False
    supports_filter_help: bool = True
    focus_prefix: str | None = None
    filter_help: str | None = None


TUI_DOMAIN_CONTROLLERS: tuple[TuiDomainController, ...] = (
    TuiDomainController(
        key="status",
        tab_id="tab_status",
        label="Landing / Status",
        switch_keywords=("switch", "go", "goto", "tab", "status", "landing"),
        supports_refresh=True,
        supports_export=True,
        filter_help=(
            "Status tab has no list filters; use Refresh to update diagnostics and "
            "cache/runtime indicators."
        ),
    ),
    TuiDomainController(
        key="scenarios",
        tab_id="tab_scenarios",
        label="Scenarios",
        switch_keywords=("switch", "go", "goto", "tab", "scenarios"),
        supports_refresh=True,
        supports_paging=True,
        supports_export=True,
        supports_focus=True,
        focus_prefix="scenarios",
        filter_help=(
            "Scenario filters: search, tag, name, order_by, modified_after, mitre_platforms, "
            "hierarchy, object_fingerprint, parameters_description, "
            "scenario_template_instance. Example: sort=name dir=asc tag=windows"
        ),
    ),
    TuiDomainController(
        key="assessments",
        tab_id="tab_assessments",
        label="Assessments",
        switch_keywords=("switch", "go", "goto", "tab", "assessments"),
        supports_refresh=True,
        supports_paging=True,
        supports_export=True,
        supports_focus=True,
        focus_prefix="assessments",
        filter_help=(
            "Assessment filters: search, name, id__in (id), tag_id, tag_ids, "
            "asset_group_id, blueprint_id, execution_strategy (strategy), "
            "has_default_schedule, use_scenario_alert_rules, version, zones_ordering, "
            "sort=<id|name|type|status|updated>, dir=<asc|desc>. "
            "Example: tag_id=<id> strategy=1 sort=name dir=asc"
        ),
    ),
    TuiDomainController(
        key="tests",
        tab_id="tab_tests",
        label="Tests",
        switch_keywords=("switch", "go", "goto", "tab", "tests"),
        supports_refresh=True,
        supports_paging=True,
        supports_export=True,
        supports_focus=True,
        focus_prefix="tests",
        filter_help=(
            "Test filters: search/name, project_template_test_id (template), "
            "use_hosted_agent, run_in_hosted_agent_preferably (prefer_hosted), "
            "sort=<id|name|project|runnable|updated>, dir=<asc|desc>. "
            "Example: name=Credential sort=name dir=asc"
        ),
    ),
    TuiDomainController(
        key="assets",
        tab_id="tab_assets",
        label="Assets",
        switch_keywords=("switch", "go", "goto", "tab", "assets"),
        supports_refresh=True,
        supports_paging=True,
        supports_export=True,
        supports_focus=True,
        focus_prefix="assets",
        filter_help=(
            "Asset filters: search, hostname, ipv4_address, ipv6_address, "
            "deployment_state_id (state), asset_group (group), activity_type (type), "
            "ordering (order_by), deepsurface_sync_state, "
            "deepsurface_last_seen_in_host_analysis_at, "
            "deepsurface_sync_state_changed_at, sort=<id|hostname|type|state|updated>, "
            "dir=<asc|desc>. "
            "Example: search=agent state=2 sort=hostname"
        ),
    ),
    TuiDomainController(
        key="results",
        tab_id="tab_results",
        label="Results",
        switch_keywords=("switch", "go", "goto", "tab", "results"),
        supports_refresh=True,
        supports_paging=True,
        supports_export=True,
        supports_focus=True,
        focus_prefix="results",
        filter_help=(
            "Results filters: sort=<id|scenario|outcome|completed|key|source|count>, "
            "dir=<asc|desc>, outcome=<text>, source=<result_summary_id|scenario_job_id>, "
            "key=<text>. Example: sort=scenario dir=asc outcome=pass"
        ),
    ),
    TuiDomainController(
        key="settings",
        tab_id="tab_settings",
        label="Settings",
        switch_keywords=("switch", "go", "goto", "tab", "settings"),
        supports_refresh=True,
        supports_paging=True,
        supports_export=True,
        supports_focus=True,
        focus_prefix="settings",
        filter_help=(
            "Settings filters: search, key, value, source, category, "
            "sort=<key|value|source|category>, dir=<asc|desc>. "
            "Example: category=runtime sort=key dir=asc"
        ),
    ),
)

READ_ONLY_COMMAND_IDS = frozenset(
    {
        "cache:clear",
        "cache:stats",
        "export:csv",
        "export:json",
        "filter-help",
        "focus:filter",
        "focus:search",
        "help",
        "page:next",
        "page:prev",
        "refresh",
        *[f"switch:{domain.key}" for domain in TUI_DOMAIN_CONTROLLERS],
    }
)

_DOMAIN_BY_KEY = {domain.key: domain for domain in TUI_DOMAIN_CONTROLLERS}
_DOMAIN_BY_TAB_ID = {domain.tab_id: domain for domain in TUI_DOMAIN_CONTROLLERS}
_SWITCH_COMMAND_IDS = {f"switch:{domain.key}" for domain in TUI_DOMAIN_CONTROLLERS}


def build_command_palette_entries() -> list[CommandPaletteEntry]:
    entries = [
        CommandPaletteEntry(
            f"switch:{domain.key}",
            f"Switch tab: {domain.label}",
            "Tabs",
            shortcut="[ ]",
            keywords=domain.switch_keywords,
        )
        for domain in TUI_DOMAIN_CONTROLLERS
    ]
    entries.extend(
        [
            CommandPaletteEntry(
                "refresh",
                "Refresh current tab",
                "Data",
                shortcut="r",
                keywords=("reload", "refresh", "sync"),
            ),
            CommandPaletteEntry(
                "cache:clear",
                "Clear all TUI caches",
                "Data",
                shortcut="-",
                keywords=("cache", "clear", "reset", "invalidate"),
            ),
            CommandPaletteEntry(
                "cache:stats",
                "Show TUI cache stats",
                "Data",
                shortcut="-",
                keywords=("cache", "stats", "status", "counts", "diagnostics"),
            ),
            CommandPaletteEntry(
                "page:next",
                "Next page",
                "Data",
                shortcut="n",
                keywords=("page", "next", "forward"),
            ),
            CommandPaletteEntry(
                "page:prev",
                "Previous page",
                "Data",
                shortcut="p",
                keywords=("page", "previous", "back"),
            ),
            CommandPaletteEntry(
                "export:json",
                "Export current view as JSON",
                "Data",
                shortcut="e",
                keywords=("export", "json", "save"),
            ),
            CommandPaletteEntry(
                "export:csv",
                "Export current view as CSV",
                "Data",
                shortcut="c",
                keywords=("export", "csv", "save"),
            ),
            CommandPaletteEntry(
                "focus:search",
                "Focus search input",
                "Focus",
                shortcut="Tab",
                keywords=("focus", "search", "find"),
            ),
            CommandPaletteEntry(
                "focus:filter",
                "Focus structured filter input",
                "Focus",
                shortcut="Tab",
                keywords=("focus", "filter", "structured"),
            ),
            CommandPaletteEntry(
                "filter-help",
                "Show filter help for current tab",
                "Help",
                shortcut="? / h",
                keywords=("help", "filter", "syntax", "examples"),
            ),
            CommandPaletteEntry(
                "help",
                "Toggle keyboard help overlay",
                "Help",
                shortcut="? / h",
                keywords=("help", "keys", "keyboard", "shortcuts"),
            ),
        ]
    )
    return entries


def allowed_command_ids_for_tab(tab_id: str) -> set[str]:
    allowed = {*_SWITCH_COMMAND_IDS, "help", "cache:clear", "cache:stats"}
    domain = _DOMAIN_BY_TAB_ID.get(tab_id)
    if domain is None:
        return allowed
    if domain.supports_refresh:
        allowed.add("refresh")
    if domain.supports_paging:
        allowed.update({"page:next", "page:prev"})
    if domain.supports_export:
        allowed.update({"export:json", "export:csv"})
    if domain.supports_focus:
        allowed.update({"focus:search", "focus:filter"})
    if domain.supports_filter_help:
        allowed.add("filter-help")
    return allowed


def filter_help_for_tab(tab_id: str) -> str | None:
    domain = _DOMAIN_BY_TAB_ID.get(tab_id)
    if domain is None:
        return None
    return domain.filter_help


def focus_prefix_for_tab(tab_id: str) -> str | None:
    domain = _DOMAIN_BY_TAB_ID.get(tab_id)
    if domain is None:
        return None
    return domain.focus_prefix


def tab_id_for_short_name(short_name: str) -> str | None:
    domain = _DOMAIN_BY_KEY.get(short_name)
    if domain is None:
        return None
    return domain.tab_id
