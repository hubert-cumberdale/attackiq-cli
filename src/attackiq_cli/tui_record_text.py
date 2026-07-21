from __future__ import annotations

from typing import Any


def _extract_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        extracted = str(value.get("id") or value.get("uuid") or "")
        return extracted or None
    if isinstance(value, int | float):
        return str(int(value))
    return str(value)


def _extract_assessment_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("assessment_id") or item.get("uuid")
    return _extract_id(value)


def _assessment_name(item: dict[str, Any]) -> str:
    value = item.get("name") or item.get("display_name")
    if value:
        return str(value)
    assessment_id = _extract_assessment_id(item)
    return assessment_id or "Unnamed assessment"


def _assessment_type(item: dict[str, Any]) -> str | None:
    raw = item.get("assessment_type")
    if isinstance(raw, dict):
        value = raw.get("name") or raw.get("display_name") or raw.get("id") or raw.get("uuid")
        return str(value) if value else None
    if raw is not None and str(raw).strip():
        return str(raw)
    fallback = item.get("assessment_type_name") or item.get("assessment_type_id")
    if fallback is not None and str(fallback).strip():
        return str(fallback)
    return None


def _build_assessment_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    assessment_id = _extract_assessment_id(item)
    if assessment_id:
        lines.append(f"Assessment ID: {assessment_id}")
    lines.append(f"Name: {_assessment_name(item)}")
    assessment_type = _assessment_type(item)
    if assessment_type:
        lines.append(f"Type: {assessment_type}")
    status = item.get("status")
    if status:
        lines.append(f"Status: {status}")
    created = item.get("created") or item.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = item.get("modified") or item.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_assessment_config(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("execution_strategy") is not None:
        lines.append(f"Execution strategy: {item.get('execution_strategy')}")
    if item.get("zones_ordering") is not None:
        lines.append(f"Zones ordering: {item.get('zones_ordering')}")
    if item.get("report_instance_type"):
        lines.append(f"Report instance type: {item.get('report_instance_type')}")
    if item.get("version") is not None:
        lines.append(f"Version: {item.get('version')}")
    if item.get("has_default_schedule") is not None:
        lines.append(f"Has default schedule: {item.get('has_default_schedule')}")
    return "\n".join(lines) if lines else "No configuration details available."


def _build_assessment_execution(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("asset_group_id"):
        lines.append(f"Asset group: {item.get('asset_group_id')}")
    if item.get("blueprint_id"):
        lines.append(f"Blueprint: {item.get('blueprint_id')}")
    if item.get("use_scenario_alert_rules") is not None:
        lines.append(f"Use scenario alert rules: {item.get('use_scenario_alert_rules')}")
    last_run = item.get("last_run") or item.get("last_execution")
    if isinstance(last_run, dict):
        run_id = last_run.get("id") or last_run.get("uuid")
        if run_id:
            lines.append(f"Last run: {run_id}")
    elif last_run:
        lines.append(f"Last run: {last_run}")
    return "\n".join(lines) if lines else "No execution details available."


def _extract_asset_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("asset_id") or item.get("uuid")
    return _extract_id(value)


def _asset_hostname(item: dict[str, Any]) -> str:
    value = item.get("hostname") or item.get("name")
    if value:
        return str(value)
    asset_id = _extract_asset_id(item)
    return asset_id or "Unnamed asset"


def _asset_deployment_state(item: dict[str, Any]) -> str | None:
    value = item.get("deployment_state")
    if isinstance(value, dict):
        resolved = value.get("name") or value.get("display_name") or value.get("id")
        return str(resolved) if resolved else None
    if value is not None and str(value).strip():
        return str(value)
    fallback = item.get("deployment_state_id")
    if fallback is not None and str(fallback).strip():
        return str(fallback)
    return None


def _build_asset_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    asset_id = _extract_asset_id(item)
    if asset_id:
        lines.append(f"Asset ID: {asset_id}")
    lines.append(f"Hostname: {_asset_hostname(item)}")
    if item.get("activity_type"):
        lines.append(f"Activity type: {item.get('activity_type')}")
    state = _asset_deployment_state(item)
    if state:
        lines.append(f"Deployment state: {state}")
    modified = item.get("modified") or item.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_asset_network(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("ipv4_address"):
        lines.append(f"IPv4: {item.get('ipv4_address')}")
    if item.get("ipv6_address"):
        lines.append(f"IPv6: {item.get('ipv6_address')}")
    if item.get("deepsurface_id"):
        lines.append(f"Deepsurface ID: {item.get('deepsurface_id')}")
    if item.get("testpoint_id"):
        lines.append(f"Testpoint ID: {item.get('testpoint_id')}")
    return "\n".join(lines) if lines else "No network details available."


def _build_asset_status(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("risk"):
        lines.append(f"Risk: {item.get('risk')}")
    if item.get("risk_score") is not None:
        lines.append(f"Risk score: {item.get('risk_score')}")
    if item.get("last_seen_discovery"):
        lines.append(f"Last seen discovery: {item.get('last_seen_discovery')}")
    if item.get("deepsurface_scanned") is not None:
        lines.append(f"Deepsurface scanned: {item.get('deepsurface_scanned')}")
    return "\n".join(lines) if lines else "No status details available."


def _extract_test_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("test_id") or item.get("uuid")
    return _extract_id(value)


def _test_name(item: dict[str, Any]) -> str:
    value = item.get("name") or item.get("display_name")
    if value:
        return str(value)
    test_id = _extract_test_id(item)
    return test_id or "Unnamed test"


def _test_project(item: dict[str, Any]) -> str | None:
    project = item.get("project")
    if isinstance(project, dict):
        value = project.get("name") or project.get("display_name") or project.get("id")
        return str(value) if value else None
    if project is not None and str(project).strip():
        return str(project)
    return None


def _build_test_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    test_id = _extract_test_id(item)
    if test_id:
        lines.append(f"Test ID: {test_id}")
    lines.append(f"Name: {_test_name(item)}")
    project = _test_project(item)
    if project:
        lines.append(f"Project: {project}")
    created = item.get("created") or item.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = item.get("modified") or item.get("updated_at")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No metadata available."


def _build_test_config(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("runnable") is not None:
        lines.append(f"Runnable: {item.get('runnable')}")
    if item.get("order") is not None:
        lines.append(f"Order: {item.get('order')}")
    if item.get("use_hosted_agent") is not None:
        lines.append(f"Use hosted agent: {item.get('use_hosted_agent')}")
    if item.get("use_pool_agent") is not None:
        lines.append(f"Use pool agent: {item.get('use_pool_agent')}")
    return "\n".join(lines) if lines else "No configuration details available."


def _build_test_execution(item: dict[str, Any]) -> str:
    lines: list[str] = []
    if item.get("scheduled_count") is not None:
        lines.append(f"Scheduled count: {item.get('scheduled_count')}")
    if item.get("using_default_assets") is not None:
        lines.append(f"Using default assets: {item.get('using_default_assets')}")
    if item.get("using_default_schedule") is not None:
        lines.append(f"Using default schedule: {item.get('using_default_schedule')}")
    if item.get("has_scenario_modules") is not None:
        lines.append(f"Has scenario modules: {item.get('has_scenario_modules')}")
    return "\n".join(lines) if lines else "No execution details available."


def _extract_scenario_id(item: dict[str, Any]) -> str | None:
    value = item.get("id") or item.get("scenario_id") or item.get("uuid")
    return _extract_id(value)


def _scenario_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("scenario_name") or item.get("scenario") or "")


def _build_scenario_metadata(item: dict[str, Any]) -> str:
    lines: list[str] = []
    scenario_id = _extract_scenario_id(item)
    if scenario_id:
        lines.append(f"Scenario ID: {scenario_id}")
    name = _scenario_name(item)
    if name:
        lines.append(f"Name: {name}")
    scenario_type = item.get("scenario_type") or item.get("scenario_type_id") or item.get("type")
    if scenario_type:
        lines.append(f"Type: {scenario_type}")
    status = item.get("status") or item.get("state")
    if status:
        lines.append(f"Status: {status}")
    created = item.get("created") or item.get("created_at")
    if created:
        lines.append(f"Created: {created}")
    modified = item.get("modified") or item.get("updated_at") or item.get("last_updated")
    if modified:
        lines.append(f"Updated: {modified}")
    return "\n".join(lines) if lines else "No scenario metadata available."


def _build_scenario_description(item: dict[str, Any]) -> str:
    description = item.get("description") or item.get("summary") or item.get("details")
    if description:
        return str(description)
    return "No description available."


def _build_scenario_tags(item: dict[str, Any]) -> str:
    tags = item.get("tags") or item.get("tag") or []
    if not tags:
        return "No tags available."
    values: list[str] = []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict):
                value = tag.get("name") or tag.get("display_name") or tag.get("id")
                if value:
                    values.append(str(value))
            else:
                values.append(str(tag))
    elif isinstance(tags, dict):
        value = tags.get("name") or tags.get("display_name") or tags.get("id")
        if value:
            values.append(str(value))
    else:
        values.append(str(tags))
    if not values:
        return "No tags available."
    preview = ", ".join(values[:8])
    if len(values) > 8:
        preview = f"{preview}, +{len(values) - 8} more"
    return preview


def _build_scenario_parameters(item: dict[str, Any]) -> str:
    value = item.get("parameters_description")
    if value:
        return str(value)
    parameters = item.get("parameters")
    if isinstance(parameters, dict):
        keys = sorted(str(key) for key in parameters if str(key).strip())
        if not keys:
            return "No parameters available."
        preview = ", ".join(keys[:8])
        if len(keys) > 8:
            preview = f"{preview}, +{len(keys) - 8} more"
        return f"Keys: {preview}"
    if isinstance(parameters, list):
        if not parameters:
            return "No parameters available."
        names: list[str] = []
        for entry in parameters:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("key") or entry.get("id")
                if name:
                    names.append(str(name))
            else:
                names.append(str(entry))
        if not names:
            return "No parameters available."
        preview = ", ".join(names[:8])
        if len(names) > 8:
            preview = f"{preview}, +{len(names) - 8} more"
        return preview
    if parameters not in (None, ""):
        return str(parameters)
    return "No parameters available."


def _build_scenario_relationships(item: dict[str, Any]) -> str:
    lines: list[str] = []
    capabilities = item.get("capabilities")
    if isinstance(capabilities, list):
        names: list[str] = []
        for capability in capabilities:
            if isinstance(capability, dict):
                value = (
                    capability.get("display_name")
                    or capability.get("name")
                    or capability.get("id")
                )
                if value:
                    names.append(str(value))
            elif capability:
                names.append(str(capability))
        if names:
            preview = ", ".join(names[:6])
            if len(names) > 6:
                preview = f"{preview}, +{len(names) - 6} more"
            lines.append(f"Capabilities: {preview}")
    template_instance = item.get("scenario_template_instance")
    if template_instance:
        lines.append(f"Template Instance: {template_instance}")
    tag_sets = item.get("scenario_tags") or item.get("tags")
    if isinstance(tag_sets, list):
        lines.append(f"Tag Relations: {len(tag_sets)}")
    assessments = item.get("assessments")
    if isinstance(assessments, list):
        lines.append(f"Assessments: {len(assessments)}")
    if not lines:
        return "No relationships available."
    return "\n".join(lines)


def _build_scenario_config(item: dict[str, Any]) -> str:
    fields = [
        ("MITRE Platforms", item.get("mitre_platforms")),
        ("Hierarchy", item.get("hierarchy")),
        ("Fingerprint", item.get("object_fingerprint") or item.get("fingerprint")),
        ("Parameters", item.get("parameters_description") or item.get("parameters")),
        ("Template Instance", item.get("scenario_template_instance")),
    ]
    lines = []
    for label, value in fields:
        if value in (None, ""):
            continue
        if isinstance(value, list):
            value = ", ".join(str(entry) for entry in value)
        lines.append(f"{label}: {value}")
    return "\n".join(lines) if lines else "No configuration data available."


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
