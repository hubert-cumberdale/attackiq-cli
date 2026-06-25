# State of the AttackIQ CLI

Last updated: 2026-06-25

## Release Status

- Current production-ready release: `v0.1.25`.
- Prepared release candidate: `v0.1.26`.
- `v0.1.25` remains the latest published/tagged release until `v0.1.26` tag creation, strict public
  mirror validation, public GitHub release creation, and enterprise package promotion evidence are
  completed.
- `v0.1.26` release-candidate metadata is prepared from current `master`; no release tag, strict
  public mirror export, public GitHub release, or enterprise package promotion evidence has been
  completed for it yet.
- Release note: `v0.1.26` adds read-only assessment schedule and EDR scan schedule wrappers, TUI
  dry-run preview design/test slices, release-prep and post-download evidence checklists, expanded
  AIQ Assist MCP contract/fixture coverage, continued service/backup/TUI/Scenario Wizard
  decomposition, completed CLI command-family extraction through the remaining mixed families
  (`call`, `export`, `scenarios`, `assessments`, `tests`, `join`, and `tui`), and architecture
  documentation alignment.
- Release-candidate evidence: `.venv/bin/python scripts/quality_gate.py` passed on 2026-06-25 for
  current `master`, including dependency constraints, release governance, public safety, secret
  scan, public mirror dry run, AIQ Assist MCP gates, Ruff, mypy, 603 pytest tests, doc links, and
  MkDocs. `.venv/bin/pip-audit` and `.venv/bin/pip-audit -r constraints.txt --no-deps` reported no
  known vulnerabilities after updating the pinned `pip` and `msgpack` audit constraints.
- Current production-ready release note: `v0.1.25` adds the post-#75 roadmap slices: first
  architecture decompositions, `attackiq source-types list`, enterprise SBOM/dependency-integrity
  artifacts, allowlisted source-secret scanning, and CI/local quality-gate parity.
- Current production-ready release evidence: source and public GitHub releases were published for
  `v0.1.25`;
  enterprise package, SBOM, dependency-integrity, provenance, Artifactory-promotion,
  signing-attestation, and no-Artifactory install evidence are recorded in `docs/MAINTENANCE.md`.
- Operator runbook: `docs/PRODUCTION_OPERATOR_RUNBOOK.md`.
- Public release guidance: `docs/PUBLIC_RELEASE.md`.
- Release-prep evidence checklist: `docs/RELEASE_PREP_EVIDENCE_CHECKLIST.md`.
- No-Artifactory evidence template: `docs/NO_ARTIFACTORY_RELEASE_EVIDENCE_TEMPLATE.md`.
- Release-audit wrapper evaluation: `docs/RELEASE_AUDIT_WRAPPER_EVALUATION.md`.
- Dependency lock policy: `docs/HASH_PINNED_LOCK_EVALUATION.md`.
- Tag governance: historical tag `v1.0.0` is stale and tracked in GitHub issue #34; do not use it
  as the current release line.

## Current Capabilities

- Load the bundled OpenAPI schema or an override path to index AttackIQ operations.
- List, search, and describe operations by tag, field selection, and `operationId`.
- Invoke OpenAPI operations with validated path/query parameters, JSON bodies, optional form data,
  explicit timeouts, TLS verification, and redacted logs.
- Store config in a user config directory with environment-variable overrides for automation.
- Provide first-class read-only wrappers for tags, scenarios, assets, asset groups, blueprints,
  integrations, source types, assessment schedules, EDR scan schedules, templates, results,
  validation results, assessments, and tests.
- Provide dry-run/apply-gated mutation commands for approved assessment and test workflows.
- Export common datasets to JSON or CSV.
- Launch a read-only Textual TUI with list/detail views, structured filters, command palette,
  cache controls, and export shortcuts.
- Join AttackIQ exports with issue CSVs through deterministic local workflows.
- Validate local scenario catalogs through `attackiq catalog`.
- Capture redacted configuration backups with `attackiq backup configs`.
- Build validated enterprise package promotion artifacts from public release tags without storing
  registry credentials, include the exact `constraints.txt` install record in package artifacts,
  generate offline SBOM, dependency-integrity, and package provenance/dependency inventory
  evidence, verify generated or downloaded package artifact directories before promotion or
  install, create credential-free Artifactory promotion evidence for operator-owned uploads, create
  credential-free signing/attestation evidence for enterprise signing workflows, and verify
  generated enterprise evidence files offline.

## Configuration Backup Boundary

`attackiq backup configs` is read-only and writes redacted artifacts plus `manifest.json`. It
defaults to `integrations,source-types,detection-rules`, refuses repo-local output paths when
detectable, rejects write-like endpoint-catalog entries, and has no raw-response output mode.

Configuration-backup artifacts are planning evidence, not exact secret restoration. Secret values
must be re-entered from the authoritative secret manager during restore.
`docs/BACKUP_DOMAIN_INTAKE_OBSERVABLE_FIELD_MAPPINGS.md` selects observable field mappings as the
next endpoint-catalog backup candidate for fixture and redaction review, but it is not enabled in
default coverage.
`docs/DETECTION_RULE_WRAPPER_REVIEW.md` keeps detection/alert-rule candidates backup-only until a
future read-only wrapper has a safe summary projection, redaction contract, and service-boundary
tests.

## Public Safety Boundary

Public release preparation is now guarded by `scripts/check_public_safety.py`, which scans tracked
files and built wheels for blocked private references and disallowed packaged paths. The standard
quality gate runs this check before linting, typing, tests, and docs validation.

GitHub Actions use Node 24-compatible official action majors (`actions/checkout@v6` and
`actions/setup-python@v6`) to avoid Node 20 runner deprecation drift.

Public mirror publication is guarded by `scripts/check_public_mirror.py`, which exports a source
snapshot, writes `PUBLICATION_MANIFEST.json`, verifies the snapshot with public-safety rules, and
initializes a throwaway one-commit public repository. Strict publication runs must use a clean
tagged ref, such as `python3 scripts/check_public_mirror.py --ref vX.Y.Z`.

Source-secret scanning is guarded by `scripts/check_secret_scan.py`, which scans tracked and
untracked source text for likely committed credentials, uses the reviewed
`security/secret-scan-allowlist.json` configuration, and reports only path, line, and rule labels.

The last recorded full post-#75 CI evidence passed for merge commit
`44b2e5f2e10c155572ae3fa77104ee22b9678ff3`, including Python 3.10, 3.11, and
3.12 jobs with dependency constraints, release governance, public safety, secret scan, public mirror
dry run, AIQ Assist MCP contract gates, Ruff, mypy, pytest, doc links, and deep-dive checks.
Current `master` includes later CLI architecture extraction and documentation alignment commits,
with local `v0.1.26` release-candidate quality-gate evidence recorded above. Confirm GitHub Actions
success for the candidate commit before tag approval.

## Enterprise Package Boundary

Enterprise package promotion is guarded by `scripts/build_enterprise_package.py`, which clones the
public GitHub tag, validates the source and built wheel with the public-safety policy, copies the
wheel and `constraints.txt` into an operator-selected output directory outside the repo, writes
`SHA256SUMS`, records `ENTERPRISE_PROMOTION_MANIFEST.json`, writes
`ENTERPRISE_PACKAGE_SBOM.spdx.json`, writes `ENTERPRISE_DEPENDENCY_INTEGRITY.json`, and writes
`ENTERPRISE_PACKAGE_PROVENANCE.json`.
`scripts/verify_enterprise_package.py` independently checks the package directory manifest,
checksums, safe artifact names, wheel public-safety status, declared install constraints,
dependency integrity, SBOM, and package provenance before Artifactory upload or after download from
an enterprise package repository. Use `--require-constraints` for current enterprise package
promotion and post-download verification so missing `constraints.txt` records fail closed.
`scripts/build_artifactory_promotion_evidence.py` validates a verified package directory and writes
credential-free promotion evidence with upload filenames, SHA256 values, target paths, post-upload
verification steps, and install smoke checks.
`scripts/build_signing_attestation_evidence.py` validates a verified package directory and writes
credential-free signing evidence with subject filenames, SHA256 values, expected detached signature
files, expected attestation files, predicate requirements, and standardized external evidence field
groups for signature, attestation, and trust-root verification.
`scripts/verify_enterprise_evidence.py` re-runs package verification with required constraints,
then cross-checks generated Artifactory and signing evidence against local artifacts, package
identity, target paths, required checklists, signing subjects, expected signing outputs, and the
external signing/attestation/trust-root evidence field standard. Use `--require-artifactory
--require-signing` when both evidence files are expected for an enterprise promotion record.
`docs/NO_ARTIFACTORY_RELEASE_EVIDENCE_TEMPLATE.md` standardizes public-safe evidence for package
build, package verification, generated evidence checks, artifact digests, and local wheelhouse
install simulation when direct Artifactory access is unavailable.
`docs/RELEASE_PREP_EVIDENCE_CHECKLIST.md` standardizes pre-tag release evidence for dependency
constraints, public safety, secret scan, public mirror dry-run, dependency audit, constraints audit,
and local quality-gate results.
`docs/POST_DOWNLOAD_PACKAGE_EVIDENCE_CHECKLIST.md` standardizes final package acceptance evidence
after download by cross-checking the wheel, constraints, SBOM, dependency integrity, provenance,
signatures, attestations, trust-root verification, and install smoke evidence against one external
release record.
`docs/RELEASE_AUDIT_WRAPPER_EVALUATION.md` keeps the template plus individual validation scripts as
the current evidence standard and defers any executing release-audit wrapper until redaction,
output-location, command-manifest, and non-upload boundaries are explicit.

These scripts do not upload to Artifactory, accept registry credentials, accept signing keys, sign
artifacts, verify enterprise trust roots, or attach package artifacts to the public GitHub release.
Operators promote the generated wheel, install constraints, checksums, manifest, SBOM, dependency
integrity, provenance, optional promotion evidence, and optional signing evidence through their
approved enterprise package workflow outside this repository.

Release operators should use least-privilege GitHub, package-repository, and signing credentials
scoped to the specific release handoff. Enterprise trust-root verification, credential expiry, and
repository permission evidence remain in the enterprise release system, not in this repository.

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
attackiq source-types list --company-id <company-id> --connector-id <connector-id>
attackiq assessment-schedules list --output assessment-schedules.json
attackiq edr-scan-schedules list --enabled true --output edr-scan-schedules.json
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
