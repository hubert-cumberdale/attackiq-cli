# Enterprise BAS Workflows

Enterprise BAS content is currently split across AttackIQ native scenarios and custom Scenario
Wizard packages. The long-term plan is to map both to the shared catalog contract.

## Current Inputs

- AttackIQ native scenarios from the configured tenant.
- Custom Scenario Wizard packages uploaded through `attackiq scenarios upload`.
- Manual scenario plans approved by the tenant owner.

## Current Catalog Flow

```bash
attackiq catalog validate --path catalog
attackiq catalog list --path catalog --provider aws --technique T1574.002
attackiq catalog coverage --path catalog --include-techniques
```

Catalog commands are local and read-only. The current CLI does not provide a `--domain` filter or a
`catalog plan-assessment` command; assessment planning remains a separate, approved workflow.

## Operator Workflow

1. Search tenant scenarios by technique, behavior, or control objective.
2. Create custom Scenario Wizard scenarios only for coverage gaps.
3. Upload packages with dry-run first.
4. Record custom template IDs in the catalog record.
5. Translate approved catalog selections into dry-run plans through the documented assessment
   workflow.

## Related Docs

- [Scenario upload playbook](../playbooks/scenario-upload.md)
- [AttackIQ assessment workflows](attackiq-assessment-workflows.md)
- [Catalog contract](../CATALOG_CONTRACT.md)
