# State of the AttackIQ CLI

Last updated: 2026-05-27

## Release Status

- Current production-ready release: `v0.1.24`.
- Release note: `v0.1.24` adds offline verification for generated enterprise Artifactory and
  signing evidence against the package directory before promotion records are accepted.
- Previous release: `v0.1.23` aligned generated Artifactory and signing evidence checklists with
  fail-closed `--require-constraints` package verification.
- Operator runbook: `docs/PRODUCTION_OPERATOR_RUNBOOK.md`.
- Public release guidance: `docs/PUBLIC_RELEASE.md`.
- Tag governance: historical tag `v1.0.0` is stale and tracked in GitHub issue #34; do not use it
  as the current release line.

## Current Capabilities

- Load the bundled OpenAPI schema or an override path to index AttackIQ operations.
- List, search, and describe operations by tag, field selection, and `operationId`.
- Invoke OpenAPI operations with validated path/query parameters, JSON bodies, optional form data,
  explicit timeouts, TLS verification, and redacted logs.
- Store config in a user config directory with environment-variable overrides for automation.
- Provide first-class read-only wrappers for tags, scenarios, assets, asset groups, blueprints,
  integrations, templates, results, validation results, assessments, and tests.
- Provide dry-run/apply-gated mutation commands for approved assessment and test workflows.
- Export common datasets to JSON or CSV.
- Launch a read-only Textual TUI with list/detail views, structured filters, command palette,
  cache controls, and export shortcuts.
- Join AttackIQ exports with issue CSVs through deterministic local workflows.
- Validate local scenario catalogs through `attackiq catalog`.
- Capture redacted configuration backups with `attackiq backup configs`.
- Build validated enterprise package promotion artifacts from public release tags without storing
  registry credentials, include the exact `constraints.txt` install record in package artifacts,
  generate offline package provenance/dependency inventory, verify generated or downloaded package
  artifact directories before promotion or install, create credential-free Artifactory promotion
  evidence for operator-owned uploads, create credential-free signing/attestation evidence for
  enterprise signing workflows, and verify generated enterprise evidence files offline.

## Configuration Backup Boundary

`attackiq backup configs` is read-only and writes redacted artifacts plus `manifest.json`. It
defaults to `integrations,source-types,detection-rules`, refuses repo-local output paths when
detectable, rejects write-like endpoint-catalog entries, and has no raw-response output mode.

Configuration-backup artifacts are planning evidence, not exact secret restoration. Secret values
must be re-entered from the authoritative secret manager during restore.

## Public Safety Boundary

Public release preparation is now guarded by `scripts/check_public_safety.py`, which scans tracked
files and built wheels for blocked private references and disallowed packaged paths. The standard
quality gate runs this check before linting, typing, tests, and docs validation.

GitHub Actions use Node 24-compatible official action majors (`actions/checkout@v6` and
`actions/setup-python@v6`) to avoid Node 20 runner deprecation drift.

Public mirror publication is guarded by `scripts/check_public_mirror.py`, which exports a source
snapshot, writes `PUBLICATION_MANIFEST.json`, verifies the snapshot with public-safety rules, and
initializes a throwaway one-commit public repository. Strict publication runs must use a clean
tagged ref, such as `python3 scripts/check_public_mirror.py --ref v0.1.24`.

## Enterprise Package Boundary

Enterprise package promotion is guarded by `scripts/build_enterprise_package.py`, which clones the
public GitHub tag, validates the source and built wheel with the public-safety policy, copies the
wheel and `constraints.txt` into an operator-selected output directory outside the repo, writes
`SHA256SUMS`, records `ENTERPRISE_PROMOTION_MANIFEST.json`, and writes
`ENTERPRISE_PACKAGE_PROVENANCE.json`.
`scripts/verify_enterprise_package.py` independently checks the package directory manifest,
checksums, safe artifact names, wheel public-safety status, declared install constraints, and
package provenance before Artifactory upload or after download from an enterprise package
repository. Use `--require-constraints` for current enterprise package promotion and
post-download verification so missing `constraints.txt` records fail closed.
`scripts/build_artifactory_promotion_evidence.py` validates a verified package directory and writes
credential-free promotion evidence with upload filenames, SHA256 values, target paths, post-upload
verification steps, and install smoke checks.
`scripts/build_signing_attestation_evidence.py` validates a verified package directory and writes
credential-free signing evidence with subject filenames, SHA256 values, expected detached signature
files, expected attestation files, and predicate requirements.
`scripts/verify_enterprise_evidence.py` re-runs package verification with required constraints,
then cross-checks generated Artifactory and signing evidence against local artifacts, package
identity, target paths, required checklists, signing subjects, and expected signing outputs. Use
`--require-artifactory --require-signing` when both evidence files are expected for an enterprise
promotion record.

These scripts do not upload to Artifactory, accept registry credentials, accept signing keys, sign
artifacts, verify enterprise trust roots, or attach package artifacts to the public GitHub release.
Operators promote the generated wheel, install constraints, checksums, manifest, provenance,
optional promotion evidence, and optional signing evidence through their approved enterprise
package workflow outside this repository.

Do not commit:

- tokens, cookies, HAR files, bearer headers, or signed URLs
- raw tenant responses or screenshots containing tenant data
- generated scenario packages, runtime caches, live-smoke evidence, or backup output directories
- local workstation paths or private repository names

## CLI Surface Area

Representative commands:

```bash
attackiq spec list --limit 10
attackiq spec show <operation-id>
attackiq call <operation-id> --param page=1 --param page_size=20
attackiq config validate
attackiq integrations list --status ACTIVE
attackiq backup configs --output-dir /tmp/aiq-config-backup-20260522T120000Z
attackiq catalog validate --path catalog
attackiq export assessments --output assessments.csv
attackiq tui
```

See `README.md` for the complete command overview and workflow examples.

## Known Limitations

- Request body validation is intentionally lightweight; complex semantic validation remains
  server-authoritative.
- Most first-class list commands fetch one explicit page unless documented otherwise.
- The TUI is read-only.
- Scenario upload and assessment/test mutation commands are dry-run by default; `--apply` performs
  the network request where supported.
- Endpoint-catalog backup domains must be sanitized, reviewed, fixture-backed, and read-only before
  use.
