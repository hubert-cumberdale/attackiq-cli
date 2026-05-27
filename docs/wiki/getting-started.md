# Getting Started

## Install for Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

Verify the entrypoint:

```bash
attackiq --version
attackiq --help
```

## Configure

Use environment variables for automation:

```bash
export ATTACKIQ_BASE_URL="https://your-tenant.example/api"
export ATTACKIQ_ACCOUNT_TOKEN="<token>"
attackiq config validate
```

For local interactive use, `attackiq auth set` and `attackiq config set` store settings in the
platform user config directory with restrictive permissions where supported.

## First Commands

```bash
attackiq spec list --limit 10 --fields operation_id,method,path
attackiq tags list --page 1 --page-size 5
attackiq scenarios list --page 1 --page-size 5
attackiq assets list --page 1 --page-size 5
```

Use `--output` for files and keep tenant data outside git.

## Production And Release Prep

- Review [Production operator runbook](../PRODUCTION_OPERATOR_RUNBOOK.md) before tenant use.
- Review [Configuration backup runbook](../CONFIGURATION_BACKUP_RUNBOOK.md) before running
  `attackiq backup configs`.
- Review [Public release and enterprise delivery](../PUBLIC_RELEASE.md) before publishing source
  or promoting wheels to an enterprise package repository.
