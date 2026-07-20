from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from attackiq_cli.tui_record_text import (
    _assessment_name,
    _assessment_type,
    _asset_deployment_state,
    _asset_hostname,
    _extract_assessment_id,
    _extract_asset_id,
    _extract_id,
    _extract_scenario_id,
    _extract_test_id,
    _scenario_name,
    _test_name,
    _test_project,
)


@dataclass
class ResultsGroup:
    key: str
    source: str
    result_summary_id: str | None
    scenario_job_id: str | None
    items: list[dict[str, Any]]

    @property
    def count(self) -> int:
        return len(self.items)


def _group_by_join_key(items: list[dict[str, Any]]) -> list[ResultsGroup]:
    groups: dict[str, ResultsGroup] = {}
    for item in items:
        result_summary_id = _extract_result_summary_id(item)
        scenario_job_id = _extract_scenario_job_id(item)
        if result_summary_id:
            key = str(result_summary_id)
            source = "result_summary_id"
        elif scenario_job_id:
            key = str(scenario_job_id)
            source = "scenario_job_id"
        else:
            key = "missing"
            source = "missing"
        if key not in groups:
            groups[key] = ResultsGroup(
                key=key,
                source=source,
                result_summary_id=str(result_summary_id) if result_summary_id else None,
                scenario_job_id=str(scenario_job_id) if scenario_job_id else None,
                items=[],
            )
        groups[key].items.append(item)
    return list(groups.values())


def _extract_result_summary_id(item: dict[str, Any]) -> str | None:
    value = item.get("result_summary_id") or item.get("result_summary")
    return _extract_id(value)


def _extract_scenario_job_id(item: dict[str, Any]) -> str | None:
    value = item.get("scenario_job_id") or item.get("scenario_job")
    return _extract_id(value)


def _build_metadata(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    result_id = summary.get("id") or summary.get("result_summary_id") or summary.get(
        "result_summary"
    )
    if result_id:
        lines.append(f"Result Summary ID: {result_id}")
    scenario_job = summary.get("scenario_job_id") or summary.get("scenario_job")
    if scenario_job:
        lines.append(f"Scenario Job ID: {scenario_job}")
    run_id = summary.get("run_id") or summary.get("assessment_run_id")
    if run_id:
        lines.append(f"Run ID: {run_id}")
    created = summary.get("created") or summary.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = summary.get("modified") or summary.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_group_metadata(group: ResultsGroup) -> str:
    lines = [
        f"Join Key: {group.key}",
        f"Source: {group.source}",
        f"Items: {group.count}",
    ]
    return "\n".join(lines)


def _build_scenario_summary(item: dict[str, Any]) -> str:
    lines: list[str] = []
    name = item.get("scenario_name") or item.get("scenario")
    if isinstance(name, dict):
        name = name.get("name") or name.get("id")
    if name:
        lines.append(f"Scenario: {name}")
    scenario_id = item.get("scenario_id")
    if scenario_id:
        lines.append(f"Scenario ID: {scenario_id}")
    scenario_type = item.get("scenario_type") or item.get("scenario_type_id")
    if scenario_type:
        lines.append(f"Scenario Type: {scenario_type}")
    return "\n".join(lines) if lines else "No scenario summary available."


def _build_outcome_summary(item: dict[str, Any]) -> str:
    outcome = item.get("outcome") or item.get("status") or item.get("result")
    if outcome:
        return f"Outcome: {outcome}"
    return "No outcome available."


def _summarize_phases(phases: list[dict[str, Any]]) -> str:
    if not phases:
        return "No phases available."
    numbers = []
    for phase in phases:
        number = phase.get("phase_number") or phase.get("phase")
        if number is not None:
            numbers.append(str(number))
    suffix = ""
    if numbers:
        preview = ", ".join(numbers[:5])
        if len(numbers) > 5:
            preview = f"{preview}, +{len(numbers) - 5} more"
        suffix = f" | Phase numbers: {preview}"
    return f"Phases loaded: {len(phases)}{suffix}"


def _summarize_logs(logs: list[dict[str, Any]]) -> str:
    if not logs:
        return "No logs available."
    return f"Logs loaded: {len(logs)}"


def _missing_join_key() -> str:
    return "Not available (missing join key)."


def _resolve_join_key(group: ResultsGroup) -> tuple[str | None, str | None] | None:
    if group.result_summary_id:
        return group.result_summary_id, None
    if group.scenario_job_id:
        return None, group.scenario_job_id
    return None


def _sort_text_key(value: Any) -> tuple[bool, str]:
    if value is None:
        return True, ""
    text = str(value).strip()
    if not text:
        return True, ""
    return False, text.lower()


def _sort_scenarios_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_scenario_id(record))
        if sort_field == "name":
            return _sort_text_key(_scenario_name(record))
        if sort_field == "type":
            return _sort_text_key(record.get("scenario_type") or record.get("scenario_type_id"))
        return _sort_text_key(
            record.get("modified") or record.get("updated_at") or record.get("last_updated")
        )

    return sorted(records, key=_key, reverse=descending)


def _sort_assessment_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_assessment_id(record))
        if sort_field == "name":
            return _sort_text_key(_assessment_name(record))
        if sort_field == "type":
            return _sort_text_key(_assessment_type(record))
        if sort_field == "status":
            return _sort_text_key(record.get("status"))
        return _sort_text_key(
            record.get("modified") or record.get("updated_at") or record.get("created")
        )

    return sorted(records, key=_key, reverse=descending)


def _sort_test_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_test_id(record))
        if sort_field == "name":
            return _sort_text_key(_test_name(record))
        if sort_field == "project":
            return _sort_text_key(_test_project(record))
        if sort_field == "runnable":
            return _sort_text_key(record.get("runnable"))
        return _sort_text_key(
            record.get("modified") or record.get("updated_at") or record.get("created")
        )

    return sorted(records, key=_key, reverse=descending)


def _sort_asset_records(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(_extract_asset_id(record))
        if sort_field == "hostname":
            return _sort_text_key(_asset_hostname(record))
        if sort_field == "type":
            return _sort_text_key(record.get("activity_type"))
        if sort_field == "state":
            return _sort_text_key(_asset_deployment_state(record))
        return _sort_text_key(record.get("modified") or record.get("updated_at"))

    return sorted(records, key=_key, reverse=descending)


def _filter_settings_records(
    records: list[dict[str, str]],
    *,
    filters: dict[str, str | None],
) -> list[dict[str, str]]:
    search = (filters.get("search") or "").strip().lower()
    key_filter = (filters.get("key") or "").strip().lower()
    value_filter = (filters.get("value") or "").strip().lower()
    source_filter = (filters.get("source") or "").strip().lower()
    category_filter = (filters.get("category") or "").strip().lower()

    def _matches(record: dict[str, str]) -> bool:
        key = (record.get("key") or "").lower()
        value = (record.get("value") or "").lower()
        source = (record.get("source") or "").lower()
        category = (record.get("category") or "").lower()
        haystack = " ".join((key, value, source, category))
        if search and search not in haystack:
            return False
        if key_filter and key_filter not in key:
            return False
        if value_filter and value_filter not in value:
            return False
        if source_filter and source_filter not in source:
            return False
        return not category_filter or category_filter in category

    return [record for record in records if _matches(record)]


def _sort_settings_records(
    records: list[dict[str, str]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, str]]:
    if not sort_field:
        return records

    def _key(record: dict[str, str]) -> Any:
        return _sort_text_key(record.get(sort_field))

    return sorted(records, key=_key, reverse=descending)


def _sort_results_summaries(
    records: list[dict[str, Any]],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[dict[str, Any]]:
    if not sort_field:
        return records

    def _key(record: dict[str, Any]) -> Any:
        if sort_field == "id":
            return _sort_text_key(record.get("id") or record.get("result_summary_id"))
        if sort_field == "scenario":
            return _sort_text_key(record.get("scenario_name") or record.get("scenario"))
        if sort_field == "outcome":
            return _sort_text_key(record.get("outcome") or record.get("status"))
        return _sort_text_key(
            record.get("modified") or record.get("completed") or record.get("created")
        )

    return sorted(records, key=_key, reverse=descending)


def _filter_results_summaries(
    records: list[dict[str, Any]],
    *,
    outcome: str | None,
) -> list[dict[str, Any]]:
    if not outcome:
        return records
    normalized = outcome.strip().lower()
    if not normalized:
        return records
    return [
        record
        for record in records
        if normalized
        in str(record.get("outcome") or record.get("status") or "").strip().lower()
    ]


def _filter_results_groups(
    groups: list[ResultsGroup],
    *,
    source: str | None,
    key_query: str | None,
) -> list[ResultsGroup]:
    filtered = groups
    if source:
        filtered = [group for group in filtered if group.source == source]
    if key_query:
        normalized = key_query.strip().lower()
        if normalized:
            filtered = [group for group in filtered if normalized in group.key.lower()]
    return filtered


def _sort_results_groups(
    groups: list[ResultsGroup],
    *,
    sort_field: str | None,
    descending: bool,
) -> list[ResultsGroup]:
    if not sort_field:
        return groups

    def _key(group: ResultsGroup) -> Any:
        if sort_field == "count":
            return group.count
        if sort_field == "source":
            return _sort_text_key(group.source)
        return _sort_text_key(group.key)

    return sorted(groups, key=_key, reverse=descending)
