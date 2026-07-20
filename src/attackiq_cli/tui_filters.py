from __future__ import annotations

import shlex

from attackiq_cli.tui_provider import ResultsViewMode


def _clean_filter_value(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _parse_structured_filter(
    value: str | None,
    *,
    keys: set[str],
    aliases: dict[str, str] | None = None,
) -> dict[str, str]:
    if not value:
        return {}
    resolved_aliases = aliases or {}
    parsed: dict[str, str] = {}
    for token in shlex.split(value):
        for part in _split_structured_filter_token(token, keys=keys, aliases=resolved_aliases):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                key, raw_value = part.split("=", 1)
            elif ":" in part:
                key, raw_value = part.split(":", 1)
            else:
                continue
            key = key.strip().lower()
            raw_value = raw_value.strip()
            if not key or not raw_value:
                continue
            key = resolved_aliases.get(key, key)
            if key not in keys:
                continue
            parsed[key] = raw_value
    return parsed


def _split_structured_filter_token(
    token: str,
    *,
    keys: set[str],
    aliases: dict[str, str],
) -> list[str]:
    parts = token.split(",")
    if len(parts) == 1:
        return parts
    split_parts: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        separator = "=" if "=" in part else ":" if ":" in part else ""
        if separator:
            candidate_key = part.split(separator, 1)[0].strip().lower()
            resolved_key = aliases.get(candidate_key, candidate_key)
            if resolved_key in keys:
                split_parts.append(current)
                current = part
                continue
        current = f"{current},{part}"
    split_parts.append(current)
    return split_parts


def _parse_filter_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _parse_filter_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("integer filters must use whole-number values.") from exc


def _parse_filter_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("boolean filters must be true or false.")


_SCENARIO_FILTER_KEYS = {
    "order_by",
    "search",
    "tag",
    "name",
    "modified_after",
    "mitre_platforms",
    "hierarchy",
    "object_fingerprint",
    "parameters_description",
    "scenario_template_instance",
    "sort",
    "dir",
}

_SCENARIO_FILTER_ALIASES = {
    "order": "order_by",
    "last_updated": "modified_after",
    "updated": "modified_after",
    "mitre": "mitre_platforms",
    "fingerprint": "object_fingerprint",
    "parameters": "parameters_description",
    "template": "scenario_template_instance",
    "direction": "dir",
}

_SCENARIOS_SORT_ALIASES = {
    "id": "id",
    "name": "name",
    "scenario": "name",
    "type": "type",
    "scenario_type": "type",
    "updated": "updated",
    "modified": "updated",
}


def _parse_scenario_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_SCENARIO_FILTER_KEYS,
        aliases=_SCENARIO_FILTER_ALIASES,
    )


_ASSESSMENT_FILTER_KEYS = {
    "search",
    "asset_group_id",
    "blueprint_id",
    "execution_strategy",
    "has_default_schedule",
    "name",
    "id__in",
    "report_instance_type",
    "tag_id",
    "tag_ids",
    "use_scenario_alert_rules",
    "version",
    "zones_ordering",
    "sort",
    "dir",
}

_ASSESSMENT_FILTER_ALIASES = {
    "asset_group": "asset_group_id",
    "blueprint": "blueprint_id",
    "id": "id__in",
    "id_in": "id__in",
    "report_type": "report_instance_type",
    "tag": "tag_id",
    "tags": "tag_ids",
    "schedule": "has_default_schedule",
    "strategy": "execution_strategy",
    "alert_rules": "use_scenario_alert_rules",
    "zones": "zones_ordering",
    "order": "sort",
    "direction": "dir",
}

_ASSESSMENTS_SORT_ALIASES = {
    "id": "id",
    "name": "name",
    "type": "type",
    "assessment_type": "type",
    "status": "status",
    "updated": "updated",
    "modified": "updated",
}


def _parse_assessment_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_ASSESSMENT_FILTER_KEYS,
        aliases=_ASSESSMENT_FILTER_ALIASES,
    )


_TEST_FILTER_KEYS = {
    "search",
    "name",
    "project_template_test_id",
    "use_hosted_agent",
    "run_in_hosted_agent_preferably",
    "sort",
    "dir",
}

_TEST_FILTER_ALIASES = {
    "template": "project_template_test_id",
    "prefer_hosted": "run_in_hosted_agent_preferably",
    "order": "sort",
    "direction": "dir",
}

_TESTS_SORT_ALIASES = {
    "id": "id",
    "name": "name",
    "project": "project",
    "runnable": "runnable",
    "updated": "updated",
    "modified": "updated",
}


def _parse_test_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_TEST_FILTER_KEYS,
        aliases=_TEST_FILTER_ALIASES,
    )


_ASSET_FILTER_KEYS = {
    "search",
    "hostname",
    "ipv4_address",
    "ipv6_address",
    "deployment_state_id",
    "deepsurface_last_seen_in_host_analysis_at",
    "deepsurface_sync_state",
    "deepsurface_sync_state_changed_at",
    "asset_group",
    "activity_type",
    "ordering",
    "sort",
    "dir",
}

_ASSET_FILTER_ALIASES = {
    "ipv4": "ipv4_address",
    "ipv6": "ipv6_address",
    "state": "deployment_state_id",
    "group": "asset_group",
    "type": "activity_type",
    "order_by": "ordering",
    "deepsurface_last_seen": "deepsurface_last_seen_in_host_analysis_at",
    "deepsurface_changed": "deepsurface_sync_state_changed_at",
    "deepsurface_state": "deepsurface_sync_state",
    "order": "sort",
    "direction": "dir",
}

_ASSETS_SORT_ALIASES = {
    "id": "id",
    "hostname": "hostname",
    "name": "hostname",
    "type": "type",
    "state": "state",
    "updated": "updated",
    "modified": "updated",
}


def _parse_asset_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_ASSET_FILTER_KEYS,
        aliases=_ASSET_FILTER_ALIASES,
    )


_SETTINGS_FILTER_KEYS = {
    "search",
    "key",
    "value",
    "source",
    "category",
    "sort",
    "dir",
}

_SETTINGS_FILTER_ALIASES = {
    "order": "sort",
    "direction": "dir",
}

_SETTINGS_SORT_ALIASES = {
    "key": "key",
    "value": "value",
    "source": "source",
    "category": "category",
}


def _parse_settings_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_SETTINGS_FILTER_KEYS,
        aliases=_SETTINGS_FILTER_ALIASES,
    )


_RESULTS_FILTER_KEYS = {"sort", "dir", "outcome", "source", "key"}

_RESULTS_FILTER_ALIASES = {
    "order": "sort",
    "direction": "dir",
    "status": "outcome",
    "join_key": "key",
}

_RESULTS_SUMMARY_SORT_ALIASES = {
    "id": "id",
    "result": "id",
    "result_id": "id",
    "scenario": "scenario",
    "name": "scenario",
    "outcome": "outcome",
    "status": "outcome",
    "completed": "completed",
    "updated": "completed",
    "modified": "completed",
}

_RESULTS_GROUP_SORT_ALIASES = {
    "key": "key",
    "join_key": "key",
    "source": "source",
    "count": "count",
    "items": "count",
}

_RESULTS_SOURCE_FILTER_ALIASES = {
    "summary": "result_summary_id",
    "result": "result_summary_id",
    "result_summary": "result_summary_id",
    "result_summary_id": "result_summary_id",
    "job": "scenario_job_id",
    "scenario_job": "scenario_job_id",
    "scenario_job_id": "scenario_job_id",
    "missing": "missing",
}


def _parse_results_filter(value: str | None) -> dict[str, str]:
    return _parse_structured_filter(
        value,
        keys=_RESULTS_FILTER_KEYS,
        aliases=_RESULTS_FILTER_ALIASES,
    )


def _resolve_results_source_filter(value: str | None) -> str | None:
    if not value:
        return None
    return _RESULTS_SOURCE_FILTER_ALIASES.get(value.strip().lower())


def _normalize_sort_direction(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"desc", "descending", "reverse"}


def _resolve_scenarios_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _SCENARIOS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_assessments_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _ASSESSMENTS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_tests_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _TESTS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_assets_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _ASSETS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_settings_sort(
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    normalized = _SETTINGS_SORT_ALIASES.get(sort_value.strip().lower())
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)


def _resolve_results_sort(
    mode: ResultsViewMode,
    sort_value: str | None,
    direction: str | None,
) -> tuple[str | None, bool]:
    if not sort_value:
        return None, False
    key = sort_value.strip().lower()
    aliases = _RESULTS_SUMMARY_SORT_ALIASES
    if mode != ResultsViewMode.SUMMARIES:
        aliases = _RESULTS_GROUP_SORT_ALIASES
    normalized = aliases.get(key)
    if not normalized:
        return None, False
    return normalized, _normalize_sort_direction(direction)
