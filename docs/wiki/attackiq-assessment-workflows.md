# AttackIQ Assessment Workflows

This page tracks the operator path for common AttackIQ assessment tasks.

## Discover Content

```bash
attackiq scenarios list --search "credential"
attackiq scenarios show <scenario-id>
attackiq export scenarios --output scenarios.csv
```

## Build A Payload

```bash
attackiq build assessment from-template \
  --template-id <template-id> \
  --name "Validation Assessment" \
  --blueprint-id <blueprint-id> \
  --output create_assessment.json
```

## Preview A Mutation

Most mutation commands are dry-run by default:

```bash
attackiq assessments create-from-template \
  --template-id <template-id> \
  --name "Validation Assessment"
```

## Apply A Mutation

```bash
attackiq assessments create-from-template \
  --template-id <template-id> \
  --name "Validation Assessment" \
  --apply
```

## Export Results

```bash
attackiq export assessments --output assessments.csv
attackiq export tests --output tests.csv
```

## Related Docs

- [Scenario upload playbook](../playbooks/scenario-upload.md)
- [Export flow](../EXPORT_FLOW.md)
- [Joiner flow](../JOINER_FLOW.md)
