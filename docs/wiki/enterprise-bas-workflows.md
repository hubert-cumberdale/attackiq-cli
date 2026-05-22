# Enterprise BAS Workflows

Enterprise BAS content is currently split across AttackIQ native scenarios and custom Scenario
Wizard packages. The long-term plan is to map both to the shared catalog contract.

## Current Inputs

- AttackIQ native scenarios from the configured tenant.
- Custom Scenario Wizard packages uploaded through `attackiq scenarios upload`.
- Manual scenario plans approved by the tenant owner.

## Planned Catalog Flow

```bash
attackiq catalog list --domain enterprise
attackiq catalog coverage --domain enterprise
attackiq catalog plan-assessment --domain enterprise --technique T1574.002
```

These commands are planned.

## Operator Workflow

1. Search tenant scenarios by technique, behavior, or control objective.
2. Create custom Scenario Wizard scenarios only for coverage gaps.
3. Upload packages with dry-run first.
4. Record custom template IDs in the catalog record.
5. Generate assessment plans from catalog records.

## Related Docs

- [Scenario upload playbook](../playbooks/scenario-upload.md)
- [Catalog contract](../CATALOG_CONTRACT.md)
