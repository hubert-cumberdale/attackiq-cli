from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

CATALOG_CONTRACT_VERSION = 1
DEFAULT_CATALOG_PATH = Path("catalog")

VALID_PROVIDERS = {"aws", "azure"}
VALID_SCENARIO_STATUS = {"proposed", "validated", "lab_only"}
VALID_REALISM = {"low", "medium", "high"}
VALID_COST = {"low", "medium", "high"}
VALID_DOMAIN = {"DRV-CLOUD", "SCV-CLOUD", "CMV-CLOUD", "ITV-CLOUD", "OSV-CLOUD", "AFV-CLOUD"}
VALID_SURFACE = {"IAM", "CP", "DP", "NET", "LOG", "K8S", "CI", "SERVERLESS", "SAAS-IDP"}
VALID_PATTERN = {
    "APP-INTEGRATION",
    "DATA-EXFIL",
    "DEF-EVAS",
    "DEF-IMP",
    "ENUM",
    "EXECUTION",
    "FEDERATION-ABUSE",
    "HIERARCHY-MOD",
    "ID-ABUSE",
    "ID-ESC",
    "IMAGE-ABUSE",
    "LATERAL",
    "PERSIST",
    "PIPELINE-ABUSE",
    "POLICY-ABUSE",
    "RESOURCE-ABUSE",
    "SECRET-ACCESS",
    "SERVERLESS-ABUSE",
    "STEALTH",
    "TOKEN-ABUSE",
}
VALID_TYPE = {"ATOMIC", "CHAIN", "CONDITIONAL"}
VALID_EXEC_CLASS = {
    "attackiq_plus_custom_harness",
    "custom_harness_only",
    "documentation_only",
    "native_attackiq_candidate",
}
VALID_INVENTORY_STATUS = {"direct", "partial", "excluded"}
CONTRACT_VALID_DOMAINS = {"enterprise", "cloud", "ics", "mobile"}
CONTRACT_VALID_COVERAGE_TYPES = {
    "detection",
    "prevention",
    "telemetry",
    "validation",
    "emulation",
}
CONTRACT_VALID_SOURCE_TYPES = {
    "attackiq-native",
    "scenario-wizard",
    "catalog-only",
    "external-easm",
    "manual",
}
CONTRACT_VALID_SAFETY_LEVELS = {"benign", "guarded", "impacting", "manual-approval"}
CONTRACT_VALID_STATUSES = {"available", "planned", "gap", "deprecated", "future"}
CONTRACT_TECHNIQUE_REQUIRED_STATUSES = {"available", "planned"}

CATALOG_CSV_FIELDS = (
    "id",
    "name",
    "domain",
    "cloud_provider",
    "source_domain",
    "surface",
    "pattern",
    "technique_ids",
    "tactics",
    "status",
    "catalog_status",
    "source_type",
    "safety_level",
    "provider_execution_classification",
    "bas_suitability_score",
)


class CatalogError(ValueError):
    """Raised when a BAS catalog cannot be loaded or interpreted."""


@dataclass(frozen=True)
class BasCatalog:
    root: Path
    scenarios: list[dict[str, Any]]
    inventory: list[dict[str, Any]]
    flat_catalog: dict[str, Any] | None

    @property
    def inventory_by_id(self) -> dict[str, dict[str, Any]]:
        return {item["attack_id"]: item for item in self.inventory if item.get("attack_id")}


def resolve_catalog_root(path: Path) -> Path:
    root = path.expanduser()
    if root.name == "scenarios":
        root = root.parent
    if not root.exists():
        raise CatalogError(f"Catalog path does not exist: {root}")
    if not root.is_dir():
        raise CatalogError(f"Catalog path must be a directory: {root}")
    scenario_dir = root / "scenarios"
    if not scenario_dir.exists() or not scenario_dir.is_dir():
        raise CatalogError(f"Catalog path must contain a scenarios directory: {scenario_dir}")
    return root


def load_bas_catalog(path: Path) -> BasCatalog:
    root = resolve_catalog_root(path)
    scenarios: list[dict[str, Any]] = []
    for scenario_path in sorted((root / "scenarios").glob("*.yml")):
        try:
            data = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise CatalogError(f"{scenario_path}: invalid YAML") from exc
        if not isinstance(data, dict):
            raise CatalogError(f"{scenario_path}: expected YAML object")
        data["_path"] = str(scenario_path)
        scenarios.append(data)

    if not scenarios:
        raise CatalogError(f"No scenario YAML files found under {root / 'scenarios'}")

    inventory_path = root / "attack_cloud_inventory.json"
    inventory: list[dict[str, Any]] = []
    if inventory_path.exists():
        try:
            inventory_data = json.loads(inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogError(f"{inventory_path}: invalid JSON") from exc
        if not isinstance(inventory_data, list):
            raise CatalogError(f"{inventory_path}: expected JSON array")
        inventory = [item for item in inventory_data if isinstance(item, dict)]

    flat_catalog_path = root / "aws_azure_catalog.json"
    flat_catalog: dict[str, Any] | None = None
    if flat_catalog_path.exists():
        try:
            flat_data = json.loads(flat_catalog_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogError(f"{flat_catalog_path}: invalid JSON") from exc
        if not isinstance(flat_data, dict):
            raise CatalogError(f"{flat_catalog_path}: expected JSON object")
        flat_catalog = flat_data

    return BasCatalog(
        root=root,
        scenarios=scenarios,
        inventory=inventory,
        flat_catalog=flat_catalog,
    )


def validate_bas_catalog(catalog: BasCatalog) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    inventory_by_id = catalog.inventory_by_id

    for scenario in catalog.scenarios:
        path = scenario.get("_path", "<unknown>")
        sid = _string_value(scenario.get("id"))
        if not sid:
            errors.append(f"{path}: missing scenario id")
            continue
        if sid in seen_ids:
            errors.append(f"{path}: duplicate scenario id {sid}")
        seen_ids.add(sid)

        _require_string(errors, scenario, "title", path)
        _validate_enum(errors, scenario, "status", VALID_SCENARIO_STATUS, path)
        _validate_enum(errors, scenario, "cloud_provider", VALID_PROVIDERS, path)
        _validate_enum(errors, scenario, "domain", VALID_DOMAIN, path)
        _validate_enum(errors, scenario, "surface", VALID_SURFACE, path)
        _validate_enum(errors, scenario, "pattern", VALID_PATTERN, path)
        _validate_enum(errors, scenario, "scenario_type", VALID_TYPE, path)
        _validate_enum(errors, scenario, "realism_level", VALID_REALISM, path)
        _validate_enum(
            errors,
            scenario,
            "provider_execution_classification",
            VALID_EXEC_CLASS,
            path,
        )

        safety = _dict_value(scenario.get("safety"))
        if safety.get("cost_risk") not in VALID_COST:
            errors.append(f"{path}: invalid safety.cost_risk")
        if not isinstance(safety.get("production_safe"), bool):
            errors.append(f"{path}: missing safety.production_safe boolean")
        if not isinstance(safety.get("destructive"), bool):
            errors.append(f"{path}: missing safety.destructive boolean")
        if not safety.get("guardrails"):
            errors.append(f"{path}: missing safety.guardrails")

        execution = _dict_value(scenario.get("execution"))
        if not execution.get("summary"):
            errors.append(f"{path}: missing execution.summary")
        if execution.get("cleanup_required") and not execution.get("cleanup_steps"):
            errors.append(f"{path}: cleanup_required is true but cleanup_steps is empty")

        mitre = _dict_value(scenario.get("mitre"))
        technique = _string_value(mitre.get("technique"))
        if not technique:
            errors.append(f"{path}: missing mitre.technique")
        for attack_id in [technique, _string_value(mitre.get("subtechnique"))]:
            if attack_id and inventory_by_id and attack_id not in inventory_by_id:
                errors.append(f"{path}: unknown ATT&CK reference {attack_id}")

        detections = _dict_value(scenario.get("detections"))
        siem = _dict_value(detections.get("siem_normalization"))
        if not siem.get("required_fields"):
            errors.append(f"{path}: missing detections.siem_normalization.required_fields")

        provider = scenario.get("cloud_provider")
        if provider == "aws":
            aws_detection = _dict_value(detections.get("aws"))
            if not aws_detection.get("logs"):
                errors.append(f"{path}: AWS scenario missing telemetry log sources")
            if not aws_detection.get("event_names"):
                errors.append(f"{path}: AWS scenario missing event_names")
        elif provider == "azure":
            azure_detection = _dict_value(detections.get("azure"))
            if not azure_detection.get("logs"):
                errors.append(f"{path}: Azure scenario missing telemetry log sources")
            if not azure_detection.get("operations"):
                errors.append(f"{path}: Azure scenario missing operations")

        if not scenario.get("validations", {}).get("telemetry_assertions"):
            errors.append(f"{path}: missing validations.telemetry_assertions")

    errors.extend(_validate_inventory(catalog))
    warnings.extend(_build_catalog_warnings(catalog))
    records = normalize_catalog_records(catalog)
    errors.extend(validate_catalog_contract_records(records))

    return {
        "valid": not errors,
        "catalog_path": str(catalog.root),
        "scenario_count": len(catalog.scenarios),
        "inventory_count": len(catalog.inventory),
        "normalized_record_count": len(records),
        "providers": dict(sorted(Counter(record["cloud_provider"] for record in records).items())),
        "statuses": dict(sorted(Counter(record["catalog_status"] for record in records).items())),
        "unique_techniques": len(
            {
                technique["technique_id"]
                for record in records
                for technique in record["attack_techniques"]
            }
        ),
        "errors": errors,
        "warnings": warnings,
    }


def validate_catalog_contract_records(records: list[dict[str, Any]]) -> list[str]:
    """Validate normalized records against the portable catalog contract."""
    errors: list[str] = []
    seen_ids: set[str] = set()

    for index, record in enumerate(records, start=1):
        label = _contract_record_label(record, index)
        rid = _string_value(record.get("id"))

        if record.get("catalog_contract_version") != CATALOG_CONTRACT_VERSION:
            errors.append(f"{label}: invalid catalog_contract_version")
        if not rid:
            errors.append(f"{label}: missing id")
        elif rid in seen_ids:
            errors.append(f"{label}: duplicate id {rid}")
        if rid:
            seen_ids.add(rid)

        _require_contract_string(errors, record, "name", label)
        _validate_contract_enum(errors, record, "domain", CONTRACT_VALID_DOMAINS, label)
        _validate_contract_enum(
            errors,
            record,
            "coverage_type",
            CONTRACT_VALID_COVERAGE_TYPES,
            label,
        )
        _validate_contract_enum(errors, record, "source_type", CONTRACT_VALID_SOURCE_TYPES, label)
        _validate_contract_enum(
            errors,
            record,
            "safety_level",
            CONTRACT_VALID_SAFETY_LEVELS,
            label,
        )
        _validate_contract_enum(errors, record, "status", CONTRACT_VALID_STATUSES, label)
        _validate_contract_string_list(errors, record, "platforms", label)
        _validate_contract_attack_techniques(errors, record, label)

    return errors


def normalize_catalog_records(catalog: BasCatalog) -> list[dict[str, Any]]:
    inventory_by_id = catalog.inventory_by_id
    records = [
        _normalize_scenario(scenario, inventory_by_id)
        for scenario in catalog.scenarios
        if scenario.get("id")
    ]
    return sorted(records, key=lambda item: item["id"])


def filter_catalog_records(
    records: list[dict[str, Any]],
    *,
    provider: str | None = None,
    status: str | None = None,
    technique: str | None = None,
    surface: str | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    provider = provider.lower() if provider else None
    status = status.lower() if status else None
    technique = technique.upper() if technique else None
    surface = surface.upper() if surface else None
    search = search.lower() if search else None

    filtered: list[dict[str, Any]] = []
    for record in records:
        if provider and record["cloud_provider"] != provider:
            continue
        if status and record["catalog_status"] != status:
            continue
        if surface and record["surface"] != surface:
            continue
        if technique and technique not in {
            item["technique_id"].upper() for item in record["attack_techniques"]
        }:
            continue
        if search and search not in _record_search_text(record):
            continue
        filtered.append(record)
        if limit is not None and len(filtered) >= limit:
            break
    return filtered


def build_catalog_coverage_summary(catalog: BasCatalog) -> dict[str, Any]:
    records = normalize_catalog_records(catalog)
    by_technique: dict[str, dict[str, Any]] = {}
    for record in records:
        for technique in record["attack_techniques"]:
            technique_id = technique["technique_id"]
            entry = by_technique.setdefault(
                technique_id,
                {
                    "technique_id": technique_id,
                    "technique_name": technique.get("technique_name"),
                    "tactics": set(),
                    "providers": set(),
                    "scenario_ids": [],
                },
            )
            if technique.get("tactic"):
                entry["tactics"].add(technique["tactic"])
            entry["providers"].add(record["cloud_provider"])
            entry["scenario_ids"].append(record["id"])

    normalized_techniques = []
    for entry in by_technique.values():
        normalized_techniques.append(
            {
                "technique_id": entry["technique_id"],
                "technique_name": entry["technique_name"],
                "tactics": sorted(entry["tactics"]),
                "providers": sorted(entry["providers"]),
                "scenario_count": len(entry["scenario_ids"]),
                "scenario_ids": sorted(entry["scenario_ids"]),
            }
        )

    inventory_statuses = Counter(
        item.get("bas_simulation_status")
        for item in catalog.inventory
        if item.get("bas_simulation_status")
    )
    covered_attack_ids = {item["technique_id"] for item in normalized_techniques}
    inventory_ids = {item["attack_id"] for item in catalog.inventory if item.get("attack_id")}

    return {
        "catalog_path": str(catalog.root),
        "scenario_count": len(records),
        "inventory_count": len(catalog.inventory),
        "unique_techniques": len(normalized_techniques),
        "inventory_techniques_with_scenarios": len(covered_attack_ids & inventory_ids),
        "inventory_techniques_without_scenarios": len(inventory_ids - covered_attack_ids),
        "providers": dict(sorted(Counter(record["cloud_provider"] for record in records).items())),
        "statuses": dict(sorted(Counter(record["catalog_status"] for record in records).items())),
        "surfaces": dict(sorted(Counter(record["surface"] for record in records).items())),
        "patterns": dict(sorted(Counter(record["pattern"] for record in records).items())),
        "execution_classifications": dict(
            sorted(
                Counter(record["provider_execution_classification"] for record in records).items()
            )
        ),
        "inventory_statuses": dict(sorted(inventory_statuses.items())),
        "techniques": sorted(normalized_techniques, key=lambda item: item["technique_id"]),
    }


def catalog_records_for_csv(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    csv_records = []
    for record in records:
        csv_records.append(
            {
                "id": record["id"],
                "name": record["name"],
                "domain": record["domain"],
                "cloud_provider": record["cloud_provider"],
                "source_domain": record["source_domain"],
                "surface": record["surface"],
                "pattern": record["pattern"],
                "technique_ids": ",".join(
                    item["technique_id"] for item in record["attack_techniques"]
                ),
                "tactics": ",".join(
                    item["tactic"] for item in record["attack_techniques"] if item.get("tactic")
                ),
                "status": record["status"],
                "catalog_status": record["catalog_status"],
                "source_type": record["source_type"],
                "safety_level": record["safety_level"],
                "provider_execution_classification": record[
                    "provider_execution_classification"
                ],
                "bas_suitability_score": record.get("bas_suitability_score"),
            }
        )
    return csv_records


def _normalize_scenario(
    scenario: dict[str, Any], inventory_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    mitre = _dict_value(scenario.get("mitre"))
    technique_ids = [
        attack_id
        for attack_id in [
            _string_value(mitre.get("technique")),
            _string_value(mitre.get("subtechnique")),
        ]
        if attack_id
    ]
    tactics = [_string_value(item) for item in mitre.get("tactics", []) if _string_value(item)]
    attack_techniques = []
    for attack_id in technique_ids:
        inventory = inventory_by_id.get(attack_id, {})
        tactic_list = tactics or inventory.get("tactics", [])
        attack_techniques.append(
            {
                "tactic": ", ".join(tactic_list),
                "technique_id": attack_id,
                "technique_name": inventory.get("attack_name"),
            }
        )

    safety = _dict_value(scenario.get("safety"))
    execution = _dict_value(scenario.get("execution"))
    detections = _dict_value(scenario.get("detections"))
    provider = _string_value(scenario.get("cloud_provider")).lower()

    return {
        "catalog_contract_version": CATALOG_CONTRACT_VERSION,
        "id": scenario["id"],
        "name": scenario.get("title"),
        "domain": "cloud",
        "cloud_provider": provider,
        "platforms": [provider] if provider else [],
        "source_domain": scenario.get("domain"),
        "surface": scenario.get("surface"),
        "pattern": scenario.get("pattern"),
        "attack_techniques": attack_techniques,
        "coverage_type": "validation",
        "source_type": _source_type(scenario),
        "status": _portfolio_status(scenario),
        "catalog_status": scenario.get("status"),
        "safety_level": _safety_level(safety),
        "scenario_type": scenario.get("scenario_type"),
        "provider_execution_classification": scenario.get("provider_execution_classification"),
        "attackiq_support": scenario.get("attackiq_support"),
        "bas_suitability_score": scenario.get("bas_suitability_score"),
        "required_permissions": scenario.get("required_permissions", []),
        "provider_actions": _provider_actions(provider, detections),
        "telemetry_sources": _telemetry_sources(provider, detections),
        "cleanup_required": bool(execution.get("cleanup_required")),
        "destructive": bool(safety.get("destructive")),
        "production_safe": safety.get("production_safe"),
        "cost_risk": safety.get("cost_risk"),
        "references": scenario.get("references", {}),
        "catalog_tags": scenario.get("catalog_tags", []),
        "source_path": scenario.get("_path"),
    }


def _validate_inventory(catalog: BasCatalog) -> list[str]:
    errors: list[str] = []
    if not catalog.inventory:
        return errors

    coverage: dict[str, list[str]] = defaultdict(list)
    provider_coverage: dict[str, set[str]] = defaultdict(set)
    for scenario in catalog.scenarios:
        mitre = _dict_value(scenario.get("mitre"))
        provider = _string_value(scenario.get("cloud_provider"))
        for attack_id in [
            _string_value(mitre.get("technique")),
            _string_value(mitre.get("subtechnique")),
        ]:
            if not attack_id:
                continue
            coverage[attack_id].append(_string_value(scenario.get("id")))
            provider_coverage[attack_id].add(provider)

    for item in catalog.inventory:
        attack_id = _string_value(item.get("attack_id"))
        if not attack_id:
            errors.append("attack_cloud_inventory.json: item missing attack_id")
            continue
        status = item.get("bas_simulation_status")
        if status not in VALID_INVENTORY_STATUS:
            errors.append(f"{attack_id}: invalid bas_simulation_status")
        if status == "excluded" and not item.get("exclusion_reason"):
            errors.append(f"{attack_id}: excluded item missing exclusion_reason")
        if status in {"direct", "partial"} and not coverage.get(attack_id):
            errors.append(f"{attack_id}: simulatable item has no scenario coverage")
        if status in {"direct", "partial"}:
            if item.get("aws_applicable") and "aws" not in provider_coverage.get(attack_id, set()):
                errors.append(f"{attack_id}: AWS-applicable item missing AWS scenario coverage")
            if item.get("azure_applicable") and "azure" not in provider_coverage.get(
                attack_id, set()
            ):
                errors.append(f"{attack_id}: Azure-applicable item missing Azure scenario coverage")

    if catalog.flat_catalog is not None:
        if catalog.flat_catalog.get("inventory_count") != len(catalog.inventory):
            errors.append("aws_azure_catalog.json inventory_count mismatch")
        items = catalog.flat_catalog.get("items", [])
        if isinstance(items, list) and len(items) != len(catalog.inventory):
            errors.append("aws_azure_catalog.json items length mismatch")
    return errors


def _build_catalog_warnings(catalog: BasCatalog) -> list[str]:
    warnings: list[str] = []
    if not catalog.inventory:
        warnings.append(
            "attack_cloud_inventory.json not found; ATT&CK reference checks are limited."
        )
    if catalog.flat_catalog is None:
        warnings.append("aws_azure_catalog.json not found; flat catalog count checks are skipped.")
    return warnings


def _source_type(scenario: dict[str, Any]) -> str:
    classification = scenario.get("provider_execution_classification")
    if classification == "native_attackiq_candidate":
        return "attackiq-native"
    if classification in {"attackiq_plus_custom_harness", "custom_harness_only"}:
        return "catalog-only"
    return "manual"


def _portfolio_status(scenario: dict[str, Any]) -> str:
    status = scenario.get("status")
    if status == "validated":
        return "available"
    if status in {"proposed", "lab_only"}:
        return "planned"
    return "gap"


def _safety_level(safety: dict[str, Any]) -> str:
    if safety.get("destructive"):
        return "impacting"
    if safety.get("production_safe") is True:
        return "benign"
    return "guarded"


def _provider_actions(provider: str, detections: dict[str, Any]) -> list[str]:
    if provider == "aws":
        return list(_dict_value(detections.get("aws")).get("event_names", []))
    if provider == "azure":
        return list(_dict_value(detections.get("azure")).get("operations", []))
    return []


def _telemetry_sources(provider: str, detections: dict[str, Any]) -> list[str]:
    if provider == "aws":
        return list(_dict_value(detections.get("aws")).get("logs", []))
    if provider == "azure":
        return list(_dict_value(detections.get("azure")).get("logs", []))
    return []


def _record_search_text(record: dict[str, Any]) -> str:
    values = [
        record.get("id"),
        record.get("name"),
        record.get("source_domain"),
        record.get("surface"),
        record.get("pattern"),
        record.get("cloud_provider"),
        " ".join(record.get("catalog_tags", [])),
        " ".join(item["technique_id"] for item in record.get("attack_techniques", [])),
        " ".join(
            item.get("technique_name") or "" for item in record.get("attack_techniques", [])
        ),
    ]
    return " ".join(str(value).lower() for value in values if value)


def _require_string(
    errors: list[str], scenario: dict[str, Any], field: str, path: str
) -> None:
    if not _string_value(scenario.get(field)):
        errors.append(f"{path}: missing {field}")


def _validate_enum(
    errors: list[str],
    scenario: dict[str, Any],
    field: str,
    valid_values: set[str],
    path: str,
) -> None:
    if scenario.get(field) not in valid_values:
        errors.append(f"{path}: invalid {field}")


def _contract_record_label(record: dict[str, Any], index: int) -> str:
    source_path = _string_value(record.get("source_path"))
    if source_path:
        return source_path
    rid = _string_value(record.get("id"))
    if rid:
        return rid
    return f"record #{index}"


def _require_contract_string(
    errors: list[str],
    record: dict[str, Any],
    field: str,
    label: str,
) -> None:
    if not _string_value(record.get(field)):
        errors.append(f"{label}: missing {field}")


def _validate_contract_enum(
    errors: list[str],
    record: dict[str, Any],
    field: str,
    valid_values: set[str],
    label: str,
) -> None:
    value = _string_value(record.get(field))
    if value not in valid_values:
        errors.append(f"{label}: invalid {field}")


def _validate_contract_string_list(
    errors: list[str],
    record: dict[str, Any],
    field: str,
    label: str,
) -> None:
    value = record.get(field)
    if not isinstance(value, list) or not all(_string_value(item) for item in value):
        errors.append(f"{label}: {field} must be a non-empty list of strings")


def _validate_contract_attack_techniques(
    errors: list[str],
    record: dict[str, Any],
    label: str,
) -> None:
    value = record.get("attack_techniques")
    if not isinstance(value, list):
        errors.append(f"{label}: attack_techniques must be a list")
        return

    status = _string_value(record.get("status"))
    if status in CONTRACT_TECHNIQUE_REQUIRED_STATUSES and not value:
        errors.append(f"{label}: attack_techniques must not be empty for {status} records")

    for technique_index, technique in enumerate(value, start=1):
        technique_label = f"{label}: attack_techniques[{technique_index}]"
        if not isinstance(technique, dict):
            errors.append(f"{technique_label} must be an object")
            continue
        if not _string_value(technique.get("technique_id")):
            errors.append(f"{technique_label}: missing technique_id")
        for field in ("tactic", "technique_name"):
            if (
                field in technique
                and technique.get(field) is not None
                and not isinstance(technique.get(field), str)
            ):
                errors.append(f"{technique_label}: {field} must be a string")


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
