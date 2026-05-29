from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from attackiq_cli.client import AttackIQClient, fetch_by_ids, paginate_results

FORMAT_CHOICES = {"csv", "json"}

TEMPLATE_CSV_HEADER = [
    "template_id",
    "template_name",
    "project_name",
    "template_type_id",
    "template_type_name",
    "scenario_id",
    "scenario_name",
    "scenario_type",
    "test_id",
    "test_name",
]

TEMPLATE_FIELD_ORDER = [
    "id",
    "template_name",
    "project_name",
    "project_template_type",
    "project_template_type_id",
    "project_template_type_name",
    "num_tests",
    "num_scenarios",
    "is_av2_compatible",
    "modified",
]

TEMPLATE_TEST_FIELD_ORDER = [
    "id",
    "name",
    "description",
    "project_template",
    "scenario_count",
    "scenarios",
    "order",
    "created",
    "modified",
]

SCENARIO_FIELD_ORDER = [
    "id",
    "name",
    "scenario_type",
    "description",
    "created",
    "modified",
]

SCENARIO_EXPORT_FIELDS = [
    "id",
    "name",
    "scenario_type",
    "description",
    "created",
    "modified",
    "cancellable",
    "capabilities",
    "last_updated",
    "failure_criteria",
    "prerequisites",
    "prevention_criteria",
    "scenario_tags",
    "supported_platform",
]

ASSESSMENT_FIELD_ORDER = [
    "id",
    "name",
    "assessment_type",
    "assessment_type_id",
    "assessment_type_name",
    "status",
    "created",
    "modified",
]

TEST_FIELD_ORDER = [
    "id",
    "name",
    "description",
    "project",
    "runnable",
    "scheduled_count",
    "created",
    "modified",
    "use_hosted_agent",
    "use_pool_agent",
    "using_default_assets",
    "using_default_schedule",
    "order",
    "has_scenario_modules",
]

ASSET_FIELD_ORDER = [
    "id",
    "hostname",
    "activity_type",
    "deployment_state",
    "ipv4_address",
    "ipv6_address",
    "modified",
]

ASSET_GROUP_FIELD_ORDER = [
    "id",
    "name",
    "description",
    "user_id",
    "num_assets",
    "created",
    "modified",
    "created_by",
]

BLUEPRINT_FIELD_ORDER = [
    "id",
    "name",
    "blueprint_template",
    "company",
    "has_modules",
    "modules",
    "created",
    "modified",
    "source_content_changed",
]

INTEGRATION_CONNECTOR_FIELD_ORDER = [
    "id",
    "display_name",
    "status",
    "enabled",
    "active",
    "pending",
    "mode",
    "connector_id",
    "connector_name",
    "connector_type_id",
    "connector_type_name",
    "vendor_product_id",
    "vendor_product_name",
    "company_id",
    "company_name",
    "source_type_count",
    "last_checkin",
    "running_version",
    "created",
    "modified",
]

SOURCE_TYPE_FIELD_ORDER = [
    "id",
    "source_type_string",
    "connector_id",
    "connector_name",
    "vendor_product_id",
    "vendor_product_name",
    "company_id",
    "user_id",
    "ignore",
    "object_fingerprint",
    "syncd_on",
    "created",
    "modified",
]


def resolve_format(output: Path, file_format: str | None) -> str:
    if file_format:
        fmt = file_format.lower()
        if fmt not in FORMAT_CHOICES:
            raise ValueError(f"Unsupported format '{file_format}'. Use csv or json.")
        return fmt
    suffix = output.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    return "csv"


def write_json(output: Path | TextIO, payload: Any) -> None:
    if isinstance(output, Path):
        with output.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return
    json.dump(payload, output, indent=2, sort_keys=True)
    output.write("\n")


def normalize_csv_value(value: Any) -> str:
    if value is None:
        return ""
    text = json.dumps(value, sort_keys=True) if isinstance(value, dict | list) else str(value)
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in text:
        text = text.replace("\n", "\\n")
    return text


def fieldnames_for_records(
    records: Iterable[dict[str, Any]],
    preferred_fields: Iterable[str] | None = None,
    include_preferred_missing: bool = False,
    include_other_fields: bool = True,
) -> list[str]:
    keys: set[str] = set()
    for record in records:
        keys.update(record.keys())
    ordered: list[str] = []
    if preferred_fields:
        for field in preferred_fields:
            if field in keys or include_preferred_missing:
                ordered.append(field)
            keys.discard(field)
        if include_other_fields:
            ordered.extend(sorted(keys))
        return ordered
    ordered.extend(sorted(keys))
    return ordered


def write_csv_records(
    output: Path,
    records: list[dict[str, Any]],
    preferred_fields: Iterable[str] | None = None,
    include_preferred_missing: bool = False,
    include_other_fields: bool = True,
) -> None:
    fieldnames = fieldnames_for_records(
        records,
        preferred_fields=preferred_fields,
        include_preferred_missing=include_preferred_missing,
        include_other_fields=include_other_fields,
    )
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if fieldnames:
            writer.writerow(fieldnames)
        for record in records:
            writer.writerow([normalize_csv_value(record.get(field)) for field in fieldnames])


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _extract_description_field(description_json: Any, key: str) -> str:
    return _ensure_dict(description_json).get(key) or ""


def _extract_capabilities(capabilities: Any) -> str:
    if not isinstance(capabilities, list):
        return ""
    names: list[str] = []
    for item in capabilities:
        if not isinstance(item, dict):
            continue
        display = item.get("display_name") or item.get("name")
        if display:
            names.append(str(display))
    return ", ".join(names)


def _extract_scenario_tags(tags: Any) -> str:
    if not isinstance(tags, list):
        return ""
    names: list[str] = []
    for item in tags:
        if not isinstance(item, dict):
            continue
        tag = item.get("tag")
        if isinstance(tag, dict):
            display = tag.get("display_name") or tag.get("name")
        else:
            display = item.get("display_name") or item.get("name")
        if display:
            names.append(str(display))
    return ", ".join(names)


def _extract_supported_platform(supported_platforms: Any) -> str:
    if not isinstance(supported_platforms, dict):
        return ""
    entries: list[str] = []
    for key, value in supported_platforms.items():
        if value:
            entries.append(f"{key}{value}")
        else:
            entries.append(str(key))
    return ", ".join(entries)


def build_scenario_export_records(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for scenario in scenarios:
        description_json = scenario.get("description_json")
        records.append(
            {
                "id": scenario.get("id"),
                "name": scenario.get("name"),
                "scenario_type": scenario.get("scenario_type"),
                "description": scenario.get("description"),
                "created": scenario.get("created"),
                "modified": scenario.get("modified"),
                "cancellable": scenario.get("cancellable"),
                "capabilities": _extract_capabilities(scenario.get("capabilities")),
                "last_updated": scenario.get("last_updated"),
                "failure_criteria": _extract_description_field(
                    description_json, "failure_criteria"
                ),
                "prerequisites": _extract_description_field(description_json, "prerequisites"),
                "prevention_criteria": _extract_description_field(
                    description_json, "prevention_criteria"
                ),
                "scenario_tags": _extract_scenario_tags(scenario.get("scenario_tags")),
                "supported_platform": _extract_supported_platform(
                    scenario.get("supported_platforms")
                ),
            }
        )
    return records


def load_scenario_details(
    client: AttackIQClient,
    op,
    scenario_ids: Iterable[str],
    max_workers: int = 4,
) -> dict[str, tuple[str, str]]:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    responses = fetch_by_ids(client, op, scenario_ids, max_workers=max_workers)
    lookup: dict[str, tuple[str, str]] = {}
    for scenario_id, scenario in responses.items():
        lookup[scenario_id] = (scenario.get("name") or "", scenario.get("scenario_type") or "")
    return lookup


def load_scenario_details_lenient(
    client: AttackIQClient,
    op,
    scenario_ids: Iterable[str],
    *,
    max_workers: int = 4,
    retries: int = 0,
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    id_list = [item for item in scenario_ids if item]
    if not id_list:
        return {}, []

    import concurrent.futures

    def fetch_one(item_id: str) -> tuple[str, dict[str, Any] | None]:
        last_exc: Exception | None = None
        for _ in range(retries + 1):
            try:
                payload = client.send(
                    op,
                    path_params={"id": item_id},
                    query_params={},
                    headers={},
                ).json()
                return item_id, payload
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
        if last_exc:
            return item_id, None
        return item_id, None

    results: dict[str, tuple[str, str]] = {}
    failures: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, item_id): item_id for item_id in id_list}
        for future in concurrent.futures.as_completed(futures):
            item_id = futures[future]
            fetched_id, payload = future.result()
            if not isinstance(payload, dict):
                failures.append(item_id)
                continue
            results[fetched_id] = (
                payload.get("name") or "",
                payload.get("scenario_type") or "",
            )
    return results, failures


def load_template_tests_index(
    client: AttackIQClient,
    op,
    page_size: int,
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for test in paginate_results(client, op, page_size=page_size):
        template_id = test.get("project_template") or ""
        if not template_id:
            continue
        index.setdefault(template_id, []).append(test)
    return index


def load_template_scenarios(
    template_tests_index: dict[str, list[dict[str, Any]]],
    template_id: str,
) -> list[dict[str, str]]:
    scenarios: list[dict[str, str]] = []
    if not template_id:
        return scenarios
    for test in template_tests_index.get(template_id, []):
        test_id = test.get("id") or ""
        test_name = test.get("name") or ""
        for scenario_id in test.get("scenarios") or []:
            scenarios.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": "",
                    "scenario_type": "",
                    "test_id": test_id,
                    "test_name": test_name,
                }
            )
    return scenarios


def build_template_records(
    client: AttackIQClient,
    templates_op,
    template_tests_index: dict[str, list[dict[str, Any]]],
    page_size: int,
) -> tuple[list[dict[str, Any]], set[str]]:
    templates: list[dict[str, Any]] = []
    scenario_ids: set[str] = set()
    for template in paginate_results(client, templates_op, page_size=page_size):
        template_id = template.get("id") or ""
        template_type = template.get("project_template_type") or {}
        scenarios = load_template_scenarios(template_tests_index, template_id)
        for scenario in scenarios:
            scenario_id = scenario.get("scenario_id")
            if scenario_id:
                scenario_ids.add(scenario_id)
        templates.append(
            {
                "template_id": template_id,
                "template_name": template.get("template_name") or "",
                "project_name": template.get("project_name") or "",
                "template_type": {
                    "id": template_type.get("id") if isinstance(template_type, dict) else "",
                    "name": template_type.get("name") if isinstance(template_type, dict) else "",
                    "description": template_type.get("description")
                    if isinstance(template_type, dict)
                    else "",
                },
                "scenarios": scenarios,
            }
        )
    return templates, scenario_ids


def apply_scenario_details(
    templates: list[dict[str, Any]],
    scenario_lookup: dict[str, tuple[str, str]],
) -> None:
    for template in templates:
        for scenario in template.get("scenarios") or []:
            scenario_id = scenario.get("scenario_id")
            if not scenario_id:
                continue
            name, scenario_type = scenario_lookup.get(scenario_id, ("", ""))
            scenario["scenario_name"] = name
            scenario["scenario_type"] = scenario_type


def flatten_templates(
    templates: list[dict[str, Any]],
    include_empty: bool,
) -> list[list[str]]:
    rows: list[list[str]] = []
    for template in templates:
        template_type = template.get("template_type") or {}
        template_row_prefix = [
            template.get("template_id", ""),
            template.get("template_name", ""),
            template.get("project_name", ""),
            template_type.get("id", "") if isinstance(template_type, dict) else "",
            template_type.get("name", "") if isinstance(template_type, dict) else "",
        ]
        scenarios = template.get("scenarios") or []
        if not scenarios and include_empty:
            rows.append(template_row_prefix + ["", "", "", "", ""])
            continue
        for scenario in scenarios:
            rows.append(
                template_row_prefix
                + [
                    scenario.get("scenario_id", ""),
                    scenario.get("scenario_name", ""),
                    scenario.get("scenario_type", ""),
                    scenario.get("test_id", ""),
                    scenario.get("test_name", ""),
                ]
            )
    return rows


def write_csv_templates(
    output: Path,
    templates: list[dict[str, Any]],
    include_empty: bool,
) -> None:
    rows = flatten_templates(templates, include_empty=include_empty)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(TEMPLATE_CSV_HEADER)
        writer.writerows(rows)
