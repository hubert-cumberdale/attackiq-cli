# Production Operator Runbook

This runbook is for named operators using `attackiq-cli` in production. The current
production-ready release line is `v0.1.22` for standard documented CLI workflows. Continue to use
normal change-control and require workflow-specific approval for destructive, high-volume,
custom-scenario, or apply-mode production activity.

Lab-only health gates are not part of the production roster.

## Install

Use a clean virtual environment from a release checkout so `constraints.txt` and package metadata
come from the same tag:

```bash
git clone https://github.com/hubert-cumberdale/attackiq-cli.git
cd attackiq-cli
git checkout v0.1.22
python -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt --upgrade pip
python -m pip install -c constraints.txt .
attackiq --version
```

Expected version output:

```text
attackiq-cli version 0.1.22
```

If using an existing checkout:

```bash
git fetch --tags origin
git checkout v0.1.22
python -m pip install -c constraints.txt --upgrade pip
python -m pip install -c constraints.txt .
attackiq --version
```

Do not select the current release by sorting all tags. The historical `v1.0.0` tag is retained as
historical/non-production context; use the release line documented in `docs/STATE.md`.

### Install From Enterprise Package Repository

Before upload and after download, verify the package artifact directory, including
`constraints.txt`, checksums, promotion manifest, and package provenance, from a release checkout:

```bash
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-v0.1.22 --require-constraints
python3 scripts/build_artifactory_promotion_evidence.py \
  /tmp/attackiq-cli-enterprise-package-v0.1.22 \
  --artifactory-url https://artifactory.example.com/artifactory \
  --repository-path api/pypi/attackiq-cli-local \
  --output /tmp/attackiq-cli-enterprise-package-v0.1.22/ARTIFACTORY_PROMOTION_EVIDENCE.json
python3 scripts/build_signing_attestation_evidence.py \
  /tmp/attackiq-cli-enterprise-package-v0.1.22 \
  --signing-profile enterprise-release \
  --output /tmp/attackiq-cli-enterprise-package-v0.1.22/SIGNING_ATTESTATION_EVIDENCE.json
```

Keep generated Artifactory and signing evidence in the enterprise release record if it includes
internal repository coordinates or signing profile names; do not commit it to this repository.

If your organization has promoted the release wheel to Artifactory or another approved enterprise
package repository, install from that package index with the `constraints.txt` promoted with the
enterprise package or an approved internal constraints record:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt --upgrade pip
python -m pip install -c constraints.txt \
  --index-url <artifactory-python-index-url> \
  attackiq-cli==0.1.22
attackiq --version
attackiq config validate
```

Do not commit package-index credentials, pip config files, `.netrc` files, downloaded wheels, or
enterprise package directories.
Keep registry authentication in the approved enterprise secret manager or user-level package
configuration outside this repository.

## Configure

Prefer environment variables for production sessions:

```bash
export ATTACKIQ_BASE_URL="https://<tenant-host>"
export ATTACKIQ_ACCOUNT_TOKEN="<redacted>"
# or:
export ATTACKIQ_JWT="<redacted>"
attackiq config validate
```

`attackiq config validate` should report `Config OK` and no unexpected TLS or auth warnings.

Saved credentials are supported when local workstation policy allows them:

```bash
attackiq config set --base-url "https://<tenant-host>"
attackiq auth set --account-token "<redacted>"
attackiq config validate
```

Keep TLS verification enabled. Use `--insecure` only for an approved lab exception, never as a
routine production setting.

## Live Smoke Harness

After installation and configuration, operators can run the scripted low-risk smoke workflow. It
requires an explicit opt-in so it cannot contact a tenant by accident:

```bash
.venv/bin/python scripts/live_smoke.py --dry-run
ATTACKIQ_LIVE_SMOKE=1 .venv/bin/python scripts/live_smoke.py \
  --output-dir /tmp/aiq-cli-live-smoke-20260514
```

The harness runs `config validate`, local spec discovery, bounded read-only list checks, and
mutation call-plan generation with fake UUIDs. It does not run `--apply` commands and does not
include lab-only health gates. On success it prints only pass/fail summaries and
aggregate counts. On failure it redacts token-like values and URLs before printing captured CLI
output.

The `--output-dir` contains raw tenant inventory responses and dry-run call plans. Keep it outside
git, restrict retention to the approved evidence window, and record only redacted summaries in
issues, PRs, and handoffs.

## Approved Standard Workflows

These workflows are approved for standard production operator use with normal change-control:

- Configuration checks:
  - `attackiq config validate`
  - `attackiq config show`
- Local spec discovery:
  - `attackiq spec list --limit 3 --fields operation_id,method,path`
  - `attackiq spec show <operation_id>`
- Read-only tenant inventory with bounded pages:
  - `attackiq tags list --page 1 --page-size 5 --output /tmp/aiq-tags.json`
  - `attackiq templates list --page 1 --page-size 5 --output /tmp/aiq-templates.json`
  - `attackiq asset-groups list --page 1 --page-size 5 --output /tmp/aiq-asset-groups.json`
  - `attackiq blueprints list --page 1 --page-size 5 --output /tmp/aiq-blueprints.json`
  - `attackiq integrations list --page 1 --page-size 5 --output /tmp/aiq-integrations.json`
  - `attackiq scenarios list --page 1 --page-size 5 --output /tmp/aiq-scenarios.json`
  - `attackiq assets list --page 1 --page-size 5 --output /tmp/aiq-assets.json`
  - `attackiq assessments list --page 1 --page-size 5 --output /tmp/aiq-assessments.json`
  - `attackiq tests list --page 1 --page-size 5 --output /tmp/aiq-tests.json`
- Read-only detail lookups for known IDs:
  - `attackiq tags show <tag-id> --output /tmp/aiq-tag.json`
  - `attackiq templates show <template-id> --output /tmp/aiq-template.json`
  - `attackiq templates tests --template-id <template-id> --page 1 --page-size 5 --output /tmp/aiq-template-tests.json`
  - `attackiq asset-groups show <asset-group-id> --output /tmp/aiq-asset-group.json`
  - `attackiq assets show <asset-id> --output /tmp/aiq-asset.json`
  - `attackiq scenarios show <scenario-id> --output /tmp/aiq-scenario.json`
  - `attackiq assessments show <assessment-id> --output /tmp/aiq-assessment.json`
  - `attackiq tests show <test-id> --output /tmp/aiq-test.json`
- Bounded exports approved by the tenant owner:
  - `attackiq export scenarios --page-size 100 --format csv --output /tmp/aiq-scenarios.csv`
  - `attackiq export tests --page-size 100 --format csv --output /tmp/aiq-tests.csv`
- Redacted configuration backup approved by the tenant owner:
  - `attackiq backup configs --output-dir /tmp/aiq-config-backup-<UTC timestamp> --tenant-alias <alias> --page-size 200 --max-pages <N>`

Write outputs to `/tmp` or another approved scratch location. Do not commit API responses, tenant
hostnames, screenshots, tokens, cookies, signed URLs, or private asset data.

## Configuration Backup

Use `attackiq backup configs` for repeatable redacted configuration capture. The default domains
are `integrations,source-types,detection-rules`. The command fetches raw responses in memory,
redacts secret-like fields before writing, creates JSON artifacts plus `manifest.json`, and refuses
repo-local output directories when detectable.

Preflight:

```bash
attackiq --version
attackiq config validate
attackiq spec list --limit 3 --fields operation_id,method,path
BACKUP_DIR="/tmp/aiq-config-backup-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$BACKUP_DIR"
```

Run:

```bash
attackiq backup configs \
  --output-dir "$BACKUP_DIR" \
  --tenant-alias <alias> \
  --page-size 200 \
  --max-pages <N>
```

Current coverage:

- integrations through `v1_company_connectors_list`
- source types through `v1_source_types_list`, with company and connector IDs derived from
  integrations or supplied with `--company-id`
- detection/alert-rule candidates through `v1_unified_mitigations_with_relations_list`

Excluded from this workflow: MSSP SSO/global-property endpoints, raw connector configuration via
`attackiq call`, browser cookies/tokens/HAR files, raw response bodies, screenshots with tenant
data, and restore/apply flows.

Use the full runbook for endpoint-discovery intake and retention rules:
`docs/CONFIGURATION_BACKUP_RUNBOOK.md`.

## Dry-Run Mutation Planning

Mutation commands are dry-run by default. Operators may generate and review call plans without
additional approval when the IDs and names are non-sensitive:

```bash
attackiq assessments create \
  --name "Production Dry Run" \
  --scenario-id <known-safe-scenario-id>

attackiq tests create \
  --assessment-id <known-noncritical-assessment-id> \
  --name "Production Dry Run"

attackiq tests add-scenarios \
  <known-noncritical-test-id> \
  --scenario-id <known-safe-scenario-id>

attackiq assessments run <known-noncritical-assessment-id>
```

Inspect the call plan before any production write. Confirm operation ID, target IDs, body fields,
and expected blast radius with the tenant owner.

## Approval Boundary

Require workflow-specific approval before any of the following:

- Adding `--apply` to any mutation command.
- Running an assessment in production.
- Uploading scenarios or packaging/running custom Scenario Wizard work.
- Running high-volume exports or broad unbounded inventory collection.
- Using `--insecure`.
- Changing shared production tenant configuration.
- Running any lab-only workflow outside the approved production roster.

Before approved apply-mode production work, capture:

- named operator and approver
- UTC date and maintenance window
- exact CLI version
- redacted dry-run call plan
- target tenant alias and target IDs
- rollback or stop criteria

## Rollback

If a CLI release is suspected to be faulty:

1. Stop using the affected virtual environment.
2. Preserve only redacted command summaries and errors.
3. Reinstall the previous approved release from a release checkout:

```bash
git fetch --tags origin
git checkout v0.1.11
python -m venv .venv-rollback
source .venv-rollback/bin/activate
python -m pip install -c constraints.txt --upgrade pip
python -m pip install -c constraints.txt .
attackiq --version
```

4. Clear local saved credentials if workstation trust is in question:

```bash
attackiq auth clear
unset ATTACKIQ_ACCOUNT_TOKEN
unset ATTACKIQ_JWT
```

5. Record the incident, release version, command category, and redacted error summary in the
   operational evidence log.

## Evidence

For each production use, record a concise, redacted entry:

- operator and observer, if any
- UTC timestamp
- CLI version from `attackiq --version`
- tenant alias, not raw private host data when policy requires redaction
- command category, not raw secrets or full API payloads
- dry-run/apply status
- output location and retention decision
- pass/fail result and follow-up owner

Keep raw tenant outputs outside git. Use aggregate counts or sanitized snippets in docs, PRs,
issues, and handoffs.
