from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from attackiq_cli import cli
from attackiq_cli.catalog import validate_catalog_contract_records


def _write_catalog(root: Path, *, duplicate: bool = False, missing_title: bool = False) -> Path:
    catalog = root / "catalog"
    scenarios = catalog / "scenarios"
    scenarios.mkdir(parents=True)
    title_line = "" if missing_title else "title: AWS Token Abuse Validation\n"
    scenario = f"""id: AWS-DRV-CLOUD-IAM-TOKEN-ABUSE-T1550-001
{title_line}status: proposed
cloud_provider: aws
domain: DRV-CLOUD
surface: IAM
pattern: TOKEN-ABUSE
scenario_type: ATOMIC
operator_description: Validate token abuse.
required_permissions:
  - sts:GetSessionToken
provider_execution_classification: custom_harness_only
attackiq_support: custom_harness_only
bas_suitability_score: 3
mitre:
  technique: T1550
  subtechnique:
  tactics:
    - Lateral Movement
objective: Exercise AWS IAM controls.
realism_level: medium
execution:
  summary: Run bounded token validation.
  api_actions:
    - sts:GetSessionToken
  cleanup_required: true
  cleanup_steps:
    - Delete temporary session material.
detections:
  aws:
    logs:
      - CloudTrail
    event_names:
      - GetSessionToken
  azure:
    logs: []
    operations: []
  siem_normalization:
    required_fields:
      - cloud.provider
validations:
  telemetry_assertions:
    - CloudTrail should record GetSessionToken.
safety:
  destructive: false
  internet_required: false
  cost_risk: low
  production_safe: false
  guardrails:
    - Use a disposable principal.
  production_safety_rationale: Isolated test identity only.
  blast_radius: Single test identity.
references:
  attack:
    - https://attack.mitre.org/techniques/T1550
  aws_docs:
    - https://docs.aws.amazon.com/STS/latest/APIReference/API_GetSessionToken.html
  azure_docs: []
catalog_tags:
  - aws
  - T1550
"""
    (scenarios / "AWS-DRV-CLOUD-IAM-TOKEN-ABUSE-T1550-001.yml").write_text(
        scenario,
        encoding="utf-8",
    )
    if duplicate:
        (scenarios / "AWS-DRV-CLOUD-IAM-TOKEN-ABUSE-T1550-002.yml").write_text(
            scenario,
            encoding="utf-8",
        )

    inventory = [
        {
            "attack_id": "T1550",
            "attack_name": "Use Alternate Authentication Material",
            "tactics": ["Lateral Movement"],
            "aws_applicable": True,
            "azure_applicable": False,
            "bas_simulation_status": "partial",
            "primary_sources": ["https://attack.mitre.org/techniques/T1550"],
        }
    ]
    (catalog / "attack_cloud_inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    flat = {"inventory_count": 1, "items": inventory}
    (catalog / "aws_azure_catalog.json").write_text(json.dumps(flat), encoding="utf-8")
    return catalog


def test_catalog_validate_valid_fixture(tmp_path):
    catalog = _write_catalog(tmp_path)

    result = CliRunner().invoke(cli.app, ["catalog", "validate", "--path", str(catalog)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["scenario_count"] == 1
    assert payload["providers"] == {"aws": 1}
    assert payload["unique_techniques"] == 1


def test_catalog_validate_reports_errors(tmp_path):
    catalog = _write_catalog(tmp_path, duplicate=True, missing_title=True)

    result = CliRunner().invoke(cli.app, ["catalog", "validate", "--path", str(catalog)])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any("missing title" in error for error in payload["errors"])
    assert any("duplicate scenario id" in error for error in payload["errors"])


def test_catalog_contract_validation_accepts_non_cloud_placeholder():
    errors = validate_catalog_contract_records(
        [
            {
                "catalog_contract_version": 1,
                "id": "ENT-WIN-CMD-T1059-PLACEHOLDER",
                "name": "Windows Command Execution Placeholder",
                "domain": "enterprise",
                "platforms": ["windows"],
                "attack_techniques": [
                    {
                        "tactic": "Execution",
                        "technique_id": "T1059",
                        "technique_name": "Command and Scripting Interpreter",
                    }
                ],
                "coverage_type": "validation",
                "source_type": "manual",
                "safety_level": "guarded",
                "status": "planned",
            }
        ]
    )

    assert errors == []


def test_catalog_contract_validation_rejects_non_cloud_placeholder_without_technique():
    errors = validate_catalog_contract_records(
        [
            {
                "catalog_contract_version": 1,
                "id": "ENT-WIN-CMD-T1059-PLACEHOLDER",
                "name": "Windows Command Execution Placeholder",
                "domain": "enterprise",
                "platforms": ["windows"],
                "attack_techniques": [],
                "coverage_type": "validation",
                "source_type": "manual",
                "safety_level": "guarded",
                "status": "planned",
            }
        ]
    )

    assert errors == [
        "ENT-WIN-CMD-T1059-PLACEHOLDER: attack_techniques must not be empty for planned records"
    ]


def test_catalog_list_filters_and_normalizes(tmp_path):
    catalog = _write_catalog(tmp_path)

    result = CliRunner().invoke(
        cli.app,
        [
            "catalog",
            "list",
            "--path",
            str(catalog),
            "--provider",
            "aws",
            "--technique",
            "T1550",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["catalog_contract_version"] == 1
    assert payload[0]["domain"] == "cloud"
    assert payload[0]["source_domain"] == "DRV-CLOUD"
    assert payload[0]["source_type"] == "catalog-only"
    assert payload[0]["status"] == "planned"
    assert payload[0]["attack_techniques"][0]["technique_name"] == (
        "Use Alternate Authentication Material"
    )


def test_catalog_list_csv_requires_output(tmp_path):
    catalog = _write_catalog(tmp_path)

    result = CliRunner().invoke(
        cli.app,
        ["catalog", "list", "--path", str(catalog), "--output-format", "csv"],
    )

    assert result.exit_code == 1
    assert "CSV output requires --output." in result.output


def test_catalog_list_csv_writes_output(tmp_path):
    catalog = _write_catalog(tmp_path)
    output = tmp_path / "catalog.csv"

    result = CliRunner().invoke(
        cli.app,
        [
            "catalog",
            "list",
            "--path",
            str(catalog),
            "--output-format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["id"] == "AWS-DRV-CLOUD-IAM-TOKEN-ABUSE-T1550-001"
    assert rows[0]["technique_ids"] == "T1550"


def test_catalog_coverage_summary(tmp_path):
    catalog = _write_catalog(tmp_path)

    result = CliRunner().invoke(cli.app, ["catalog", "coverage", "--path", str(catalog)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["scenario_count"] == 1
    assert payload["inventory_techniques_with_scenarios"] == 1
    assert "techniques" not in payload


def test_catalog_coverage_can_include_techniques(tmp_path):
    catalog = _write_catalog(tmp_path)

    result = CliRunner().invoke(
        cli.app,
        ["catalog", "coverage", "--path", str(catalog), "--include-techniques"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["techniques"][0]["technique_id"] == "T1550"
    assert payload["techniques"][0]["scenario_count"] == 1
