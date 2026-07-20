# State of the AttackIQ CLI

Last updated: 2026-07-20

## Release Status

- Current production-ready release: `v0.1.26`.
- Prepared release candidate: `v0.1.27`.
- `v0.1.27` completes the seven approved read-only TUI previews and the identified architecture
  decomposition, enforces the 800-line source-module boundary, expands fail-closed AIQ Assist MCP
  contract and fixture guardrails while keeping consumption disabled, and aligns operator
  documentation with observable CLI behavior. It is not yet tagged, published, or promoted to the
  production-ready release line.
- `v0.1.27` pre-tag validation passed on 2026-07-20: dependency constraints and release
  governance aligned, installed and constraints-based dependency audits reported no known
  vulnerabilities, the full quality gate passed with 761 tests, and the public-mirror dry run,
  documentation links, deep-dive checks, strict MkDocs build, and whitespace check passed. Tag
  approval has not been requested.
- `v0.1.26` is the latest published/tagged release as of 2026-06-25. The source release commit is
  `bc85fc96dd663b3f230db5a077313469c3e6987b`, the public mirror snapshot is
  `ad46849452f5d63e5b84caf6df555d8120a095ae`, and tag-time CI run `28193339998` passed.
- Release note: `v0.1.26` adds read-only assessment schedule and EDR scan schedule wrappers, TUI
  dry-run preview design/test slices, release-prep and post-download evidence checklists, expanded
  AIQ Assist MCP contract/fixture coverage, continued service/backup/TUI/Scenario Wizard
  decomposition, completed CLI command-family extraction through the remaining mixed families
  (`call`, `export`, `scenarios`, `assessments`, `tests`, `join`, and `tui`), and architecture
  documentation alignment.
- Release validation evidence: `.venv/bin/python scripts/quality_gate.py` passed on 2026-06-25 for
  the `v0.1.26` source commit, including dependency constraints, release governance, public safety,
  secret scan, public mirror dry run, AIQ Assist MCP gates, Ruff, mypy, 603 pytest tests, doc links,
  and MkDocs. `.venv/bin/pip-audit` and `.venv/bin/pip-audit -r constraints.txt --no-deps`
  reported no known vulnerabilities after updating the pinned `pip` and `msgpack` audit
  constraints.
- Current production-ready release evidence: source and public GitHub releases were published for
  `v0.1.26`; strict public mirror, enterprise package, SBOM, dependency-integrity, provenance,
  Artifactory-promotion, signing-attestation, combined evidence verification, and no-Artifactory
  install evidence are recorded in `docs/MAINTENANCE.md`.
- Current project direction review: `docs/REVIEW_2026-07-08_PROJECT_DIRECTION.md` is the active
  planning checkpoint for architecture decomposition, read-only wrapper selection, backup maturity,
  AIQ Assist MCP guardrails, TUI preview scope, and supply-chain evidence posture. It does not
  prepare a release or change the current production-ready release.
- The fresh 2026-07-17 #60 selection gate explicitly selected no new wrapper family. Detection-rule
  candidates, connector setup detail, result artifacts, EDR schedule detail/runs, and other
  schedule endpoints remain deferred until exactly one named operator workflow supplies a bounded
  summary projection, sanitized fixtures, redaction/retention rules, and service-boundary scope.
  Issue #60 remains open in watch mode; no CLI or network behavior changed.
- The 2026-07-18 AIQ Assist MCP contract hardening keeps consumer code blocked after a provider
  source is merely marked documented. The gate now requires a boolean
  `allow_cli_tui_consumption`, boolean `adapter_mock_tests` evidence once the source is documented,
  and both fields set to true before source markers are allowed. The current status remains
  `pending_provider_source`, consumption and live checks remain false, provider ownership/source
  remain unset, and no MCP adapter, CLI/TUI command, or network path was added.
- The subsequent 2026-07-18 MCP fixture hardening validates that each synthetic request and
  response matches its declared success, auth/provider failure, timeout, or malformed-response
  outcome and requires an explicit redaction expectation. Corrupted or contradictory fixtures now
  fail the existing offline quality gate. These repo-local fixtures remain non-canonical planning
  evidence; provider status, consumption, live checks, and network behavior are unchanged.
- The next 2026-07-18 MCP fixture redaction hardening requires exact placeholders in sensitive
  fields, parses URLs against an exact synthetic example-host allowlist, rejects embedded URL
  credentials and deceptive hostname prefixes, and preserves the raw-transcript-key prohibition.
  Provider status remains pending; no adapter, CLI/TUI command, live check, or network path was
  added.
- The subsequent 2026-07-18 MCP fixture inventory hardening closes the fixture directory to the
  expected regular JSON case files and rejects ignored side artifacts, subdirectories, symbolic
  links, invalid roots, and filename/case drift. Provider status, consumption, live checks, and
  network behavior remain unchanged.
- The next 2026-07-18 MCP request-envelope hardening requires synthetic requests to contain only
  exact redacted authorization and JSON content-type headers, treating names case-insensitively
  while rejecting duplicates, omissions, and cookie/session-style sources. Provider status remains
  pending; no adapter, CLI/TUI command, live check, or network path was added.
- The 2026-07-19 MCP request-parameter hardening requires empty discovery params and exactly a
  non-empty synthetic name plus arguments object for tool calls. It deliberately does not assert a
  provider tool name or argument schema. Provider status, consumption, live checks, and network
  behavior remain unchanged.
- The subsequent 2026-07-19 MCP success-result hardening requires non-empty synthetic `tools` and
  `content` lists for discovery and tool-call success, respectively, while leaving list item
  schemas unconstrained until provider documentation exists. No consumption or network path was
  added.
- The next 2026-07-19 MCP failure-envelope hardening requires non-boolean integer error codes and
  non-empty messages for synthetic auth/provider failures. It deliberately leaves code values and
  their relationship to HTTP statuses unconstrained. Provider status remains pending; no adapter,
  CLI/TUI command, live check, or network path was added.
- The subsequent 2026-07-19 MCP fixture-schema hardening rejects undeclared fields in repo-owned
  fixture, expectation, request, response-transport, and timeout wrappers while leaving provider
  response bodies and nested provider data unconstrained. Provider and runtime status are
  unchanged.
- The next 2026-07-19 MCP status-range hardening bounds stored synthetic HTTP response statuses to
  100 through 599 and provider-error outcomes to 400 through 599 while allowing unassigned in-range
  values and keeping JSON-RPC error codes independent. Provider and runtime status are unchanged.
- The subsequent 2026-07-19 MCP fixture-URL hardening detects scheme-qualified URLs, permits only
  valid HTTPS on exact synthetic example hosts, and rejects other schemes, invalid ports, and URL
  credentials. Provider and runtime status are unchanged.
- The next 2026-07-19 MCP fixture-retention hardening limits each committed synthetic fixture to
  16 KiB and rejects oversized files before parsing. Provider response schemas and runtime status
  remain unchanged; raw live evidence remains outside git.
- The subsequent 2026-07-19 MCP fixture-decoding hardening rejects duplicate JSON object names at
  every nesting level before contract validation. This prevents parser-dependent fixture evidence
  while leaving provider response schemas and runtime status unchanged.
- The next 2026-07-19 MCP fixture-number hardening rejects `NaN`, `Infinity`, and `-Infinity`
  before contract validation, including inside provider-owned extension data. Finite numeric
  values, provider response schemas, and runtime status remain unchanged.
- The subsequent 2026-07-19 MCP fixture-key hardening classifies sensitive and raw-transcript
  fields from literal JSON object names, preventing dotted provider-extension keys from bypassing
  redaction or retention checks. Provider response schemas and runtime status remain unchanged.
- The next 2026-07-20 MCP fixture-placeholder hardening removes the `oauth` and `token` value
  exemption for sensitive keys. Those values remain valid in the dedicated `auth_mode` field but
  cannot satisfy redaction for sensitive keys; provider response schemas and runtime status remain
  unchanged.
- The subsequent 2026-07-20 MCP fixture numeric-overflow hardening routes JSON floating-point
  decoding through a finite-value check. Exponent forms that would decode as infinity now fail
  closed; representable finite values, provider response schemas, and runtime status remain
  unchanged.
- The first 2026-07-17 #59 TUI preview UX adds an Assessments-tab
  `preview:assessment-run` command and local modal. It validates or prefills an assessment UUID,
  reuses the CLI dry-run plan builder and redacted preview adapter, displays operation/method/path/
  params/body plus `No request sent`, and exposes no client, apply flag, mutation service, export,
  or persistence path.
- The second 2026-07-17 #59 TUI preview UX adds a Tests-tab `preview:test-status` command and
  local modal. It validates or prefills a test UUID, reuses the CLI `tests get-status` plan builder
  and redacted preview adapter, displays the GET operation/method/path/params plus
  `No request sent`, and retains the same no-client, no-apply, no-export, and no-persistence
  boundary.
- The third 2026-07-18 #59 TUI preview UX adds an Assessments-tab `preview:new-test` command and
  local modal. It validates or prefills an assessment UUID, requires and trims a test name, reuses
  the CLI `tests create` plan builder and redacted preview adapter, displays the bounded JSON body
  plus `No request sent`, and retains the no-client, no-apply, no-export, and no-persistence
  boundary.
- The fourth 2026-07-18 #59 TUI preview UX adds a Tests-tab `preview:test-scenarios` command and
  local modal. It validates or prefills a test UUID, validates and stably deduplicates one or more
  comma-separated scenario UUIDs, reuses the CLI `tests add-scenarios` plan builder and redacted
  preview adapter, bounds long scenario lists, and retains the no-client, no-apply, no-export, and
  no-persistence boundary.
- The fifth 2026-07-18 #59 TUI preview UX adds an Assessments-tab
  `preview:assessment-defaults` command and local modal. It validates or prefills an assessment
  UUID, accepts optional comma-separated asset and asset-group UUID lists while requiring at least
  one target type, stably deduplicates each list, reuses the CLI `assessments update-defaults` plan
  builder and redacted preview adapter, and retains the no-client, no-apply, no-export, and
  no-persistence boundary.
- The sixth 2026-07-18 #59 TUI preview UX adds a Scenarios-tab `preview:new-assessment` command
  and local modal. It validates or prefills a scenario UUID, accepts and stably deduplicates one
  or more comma-separated scenario UUIDs, requires and trims an assessment name, reuses the CLI
  `assessments create` plan builder and redacted preview adapter, and retains the no-client,
  no-apply, no-export, and no-persistence boundary.
- The seventh 2026-07-18 #59 TUI preview UX adds an Assessments-tab
  `preview:assessment-from-template` command and local modal. It requires and validates a template
  UUID and trimmed assessment name, accepts an optional validated blueprint UUID, reuses the CLI
  `assessments create-from-template` plan builder and redacted preview adapter, and retains the
  no-client, no-apply, no-export, and no-persistence boundary. All plans approved by the current
  TUI preview design are now implemented, and both the keyboard help overlay and Status tab state
  that previews never send requests. Further expansion requires a separate scope review.
- PR #133 merged the cumulative architecture and TUI handoff as commit
  `8ecb6ba6ee05c4ed2563a35defad2e5bba04648b` on 2026-07-18. Issue #59 closed as completed, and
  post-merge CI run `29631047260` passed on Python 3.10, 3.11, and 3.12. Any future preview
  expansion requires a new reviewed scope; this merge does not change the production-ready
  release from `v0.1.26`.
- Follow-up implementation on 2026-07-16 and 2026-07-17 completed eighteen small #55 TUI
  decomposition slices by
  extracting task lifecycle and blocking executor handoff helpers into
  `src/attackiq_cli/tui_tasks.py`, moving pure
  structured-filter parsing and sort resolution into `src/attackiq_cli/tui_filters.py`, moving
  pure record text builders into `src/attackiq_cli/tui_record_text.py`, moving pure result
  grouping and list sort/filter helpers into `src/attackiq_cli/tui_record_lists.py`, moving pure
  shortcut/palette/runtime-error display helpers into `src/attackiq_cli/tui_display.py`, moving
  shared widgets and the status tab into `src/attackiq_cli/tui_widgets.py`, moving the shared
  Textual stylesheet into `src/attackiq_cli/tui_styles.py`, moving shared TUI export path and
  file-writing helpers into `src/attackiq_cli/tui_exports.py`, moving Settings tab state,
  rendering, filtering, export actions, and record/detail builders into
  `src/attackiq_cli/tui_settings.py`, moving the Scenarios tab state, async loading, rendering,
  filtering, paging, detail, exports, and view-state restoration into
  `src/attackiq_cli/tui_scenarios.py`, moving the Assessments tab state, async loading, rendering,
  filtering, paging, detail, exports, and view-state restoration into
  `src/attackiq_cli/tui_assessments.py`, moving the Tests tab state, async loading, rendering,
  filtering, paging, detail, exports, and view-state restoration into
  `src/attackiq_cli/tui_tests.py`, moving the Assets tab state, async loading, rendering,
  filtering, paging, detail, exports, and view-state restoration into
  `src/attackiq_cli/tui_assets.py`, moving the Results tab models, state, async loading, view-mode
  grouping, rendering, filtering, paging, detail, exports, and view-state restoration into
  `src/attackiq_cli/tui_results.py`, moving the Textual app shell, tab orchestration,
  command-palette dispatch, cache/status actions, paging/export routing, help, and focus controls
  into `src/attackiq_cli/tui_app.py`, reducing `src/attackiq_cli/tui.py` from 5084 to 402 lines, and
  moving the TUI runtime state model and auth/base-URL/spec-cache/environment/workspace display
  derivation into `src/attackiq_cli/tui_provider_state.py`, reducing
  `src/attackiq_cli/tui_provider.py` from 853 to 758 lines, and
  fixing deterministic review worktree status reporting.
- The subsequent 2026-07-17 #55 Scenario Wizard slice moved create dry-run planning, isolated apply
  execution, temporary configuration transport, runtime dependency setup, and generated-file
  result collection into `src/attackiq_cli/scenario_wizard_create.py`, reducing
  `src/attackiq_cli/scenario_wizard.py` from 1531 to 1240 lines while preserving CLI behavior,
  subprocess environment isolation, redaction, and compatibility imports.
- The next 2026-07-17 #55 Scenario Wizard slice moved cache resolution, wrapper ZIP inspection,
  runtime-bundle validation summaries, bundle-copy planning, and bundle-copy apply behavior into
  `src/attackiq_cli/scenario_wizard_runtime.py`, reducing `src/attackiq_cli/scenario_wizard.py` to
  1019 lines while preserving sensitive-file suppression, validation, CLI behavior, and
  compatibility imports.
- The final 2026-07-17 #55 Scenario Wizard slice moved image-tar runtime inspection, bounded layer
  spooling, Docker whiteout/index handling, selected-file materialization, safe path normalization,
  sensitive-file exclusion, and requirements credential filtering into
  `src/attackiq_cli/scenario_wizard_image.py`, reducing `src/attackiq_cli/scenario_wizard.py` to a
  305-line orchestration and compatibility facade while preserving image prepare behavior and
  security controls.
- The final identified #55 oversized-module slice moved GitLab retry/client handling and the
  apply-gated GitLab issue-update and AttackIQ assessment-creation executors into
  `src/attackiq_cli/joiner/det_pipeline_apply.py`, reducing
  `src/attackiq_cli/joiner/det_pipeline.py` from 907 to 789 lines while preserving its imports,
  deterministic stages, artifacts, CLI behavior, explicit network timeout, and apply gate. The
  deterministic review now reports no modules above the 800-line architecture threshold.
- The 2026-07-18 #55 closeout adds a fail-closed architecture check to
  `scripts/deterministic_review.py` and runs it from both `scripts/quality_gate.py` and GitHub
  Actions. Python modules under `src/` may be at most 800 lines; focused tests prove the 800-line
  boundary passes and 801 lines fails with the offending path and count. The completed
  decomposition is now a maintained invariant rather than an open extraction queue. This does not
  change the production-ready release from `v0.1.26`.
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
  cache controls, export shortcuts, and contextual local new-assessment,
  assessment-from-template, assessment-default targets, assessment-run, new-test, test-scenario
  assignment, and test-status request previews.
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
`docs/BACKUP_DOMAIN_INTAKE_OBSERVABLE_FIELD_MAPPINGS.md` documents observable field mappings as an
optional `needs-redaction` endpoint-catalog backup domain. It requires explicit `--include` and
`--endpoint-catalog` options and is not enabled in default coverage.
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

The `v0.1.26` tag-time CI evidence passed for source commit
`bc85fc96dd663b3f230db5a077313469c3e6987b` in run `28193339998`, including Python 3.10, 3.11,
and 3.12 jobs with dependency constraints, release governance, public safety, secret scan, public
mirror dry run, AIQ Assist MCP contract gates, Ruff, mypy, pytest, doc links, deep-dive checks, tag
and package version alignment, and dependency audit. Current `master` may include later release
closeout documentation commits after the tag; rerun local and CI gates before the next tag.

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
