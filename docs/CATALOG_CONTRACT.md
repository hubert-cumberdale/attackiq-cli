# BAS Catalog Contract

This contract defines a portable scenario catalog format for local, read-only catalog ingestion.
Version 1 is file-first so teams can keep catalog content in their own approved repository or
artifact store and pass an explicit path to `attackiq catalog`.

## Contract Version

Catalog records must declare:

```yaml
catalog_contract_version: 1
```

Consumers must reject unsupported major versions.

## Required Record Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `catalog_contract_version` | integer | Contract version. Current value: `1`. |
| `id` | string | Stable catalog record ID. |
| `name` | string | Operator-facing scenario name. |
| `domain` | string | `enterprise`, `cloud`, `ics`, or `mobile`. |
| `platforms` | list[string] | Target platforms such as `aws`, `azure`, `windows`, or `linux`. |
| `attack_techniques` | list[object] | ATT&CK technique mappings. |
| `coverage_type` | string | `detection`, `prevention`, `telemetry`, `validation`, or `emulation`. |
| `source_type` | string | `attackiq-native`, `scenario-wizard`, `catalog-only`, `external-easm`, or `manual`. |
| `safety_level` | string | `benign`, `guarded`, `impacting`, or `manual-approval`. |
| `status` | string | `available`, `planned`, `gap`, `deprecated`, or `future`. |

## Recommended Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `attackiq_scenario_id` | string | Existing AttackIQ scenario ID when available. |
| `attackiq_template_id` | string | Custom scenario template ID after upload. |
| `scenario_package` | string | Relative path or artifact name for custom packages. |
| `required_controls` | list[string] | Controls expected for validation. |
| `data_sources` | list[string] | Expected telemetry or log sources. |
| `prerequisites` | list[string] | Required accounts, agents, roles, or lab conditions. |
| `references` | list[string] | Source references. |
| `notes` | string | Short operator context. |

## Technique Mapping

Each `attack_techniques` item should use:

```yaml
attack_techniques:
  - tactic: Credential Access
    technique_id: T1550.001
    technique_name: Application Access Token
```

Technique names should match the relevant ATT&CK domain when the catalog is generated.

## Example

```yaml
catalog_contract_version: 1
id: AWS-DRV-CLOUD-IAM-TOKEN-ABUSE-T1550-001
name: AWS IAM Token Abuse Validation
domain: cloud
platforms:
  - aws
attack_techniques:
  - tactic: Credential Access
    technique_id: T1550.001
    technique_name: Application Access Token
coverage_type: validation
source_type: catalog-only
safety_level: guarded
status: planned
required_controls:
  - CloudTrail
  - SIEM detection content
references:
  - https://attack.mitre.org/
notes: Validate detection coverage before adding active execution.
```

## Validation Rules

- IDs must be stable and unique within a catalog.
- `domain`, `coverage_type`, `source_type`, `safety_level`, and `status` must be allowlisted.
- `attack_techniques` must contain at least one item for available or planned records.
- `impacting` and `manual-approval` records must not be included in automatic assessment plans.
- Consumers should warn when a record has no executable AttackIQ scenario or uploaded template.

## CLI Usage

Catalog commands are read-only and perform no network calls:

```bash
attackiq catalog validate --path catalog
attackiq catalog list --path catalog --provider aws --technique T1550
attackiq catalog coverage --path catalog
```

The default path is `catalog`. Teams should pass an explicit `--path` when their catalog content
lives elsewhere.
