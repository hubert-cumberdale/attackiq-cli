# Enterprise Maturity Review
Date: 2026-05-27
Scope: architecture, CLI behavior, documentation, security, testing, CI/release governance,
enterprise delivery, public-repo readiness, and roadmap drift.

Post-review note: PR #75 completed several items that this historical review listed as future
work, including CI/local gate parity, SBOM output, dependency-integrity records, allowlisted
secret scanning, least-privilege/trust-root guidance, and the first architecture/wrapper slices.
For the post-#75 readiness update, see
`docs/REVIEW_2026-05-29_POST_75_RELEASE_READINESS.md`.

## Executive Summary

Maturity score: 8.1/10.

The repository is production-capable for documented CLI workflows and credential-free enterprise
package promotion. The strongest controls are centralized HTTP transport defaults, explicit
timeouts, TLS verification, redacted request logging, read-only defaults for most operator
workflows, dry-run/apply gates for mutation workflows, public-safety checks, release-governance
checks, and offline enterprise package/evidence verification.

The main remaining maturity risks are governance and maintainability issues rather than immediate
runtime blockers:

- CI and the local quality gate are not fully aligned.
- Several modules are large enough that feature additions carry elevated regression risk.
- Enterprise Artifactory upload, download, signing, attestation, and trust-root checks remain
  operator-run external controls.
- Supply-chain controls are good for a beta CLI, but should move toward SBOM output, hash-pinned
  constraints, secret scanning, and stronger provenance guidance before broader enterprise rollout.

## Review Inputs

Code and docs reviewed:

- `README.md`
- `docs/GOVERNANCE.md`
- `docs/STATE.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_STANDARDS.md`
- `docs/PRODUCTION_READINESS.md`
- `docs/PUBLIC_RELEASE.md`
- `docs/ARTIFACTORY_DELIVERY.md`
- `docs/PRODUCTION_OPERATOR_RUNBOOK.md`
- `docs/AIQ_ASSIST_MCP_CONTRACT.md`
- `.github/workflows/ci.yml`
- `scripts/quality_gate.py`
- enterprise package/evidence scripts
- `src/attackiq_cli/cli.py`
- `src/attackiq_cli/client.py`
- `src/attackiq_cli/services.py`
- `src/attackiq_cli/backup.py`
- `src/attackiq_cli/tui.py`
- `src/attackiq_cli/scenario_wizard.py`
- tests under `tests/`

CLI surfaces checked:

- `.venv/bin/attackiq --help`
- `.venv/bin/attackiq call --help`
- `.venv/bin/attackiq join --help`
- `.venv/bin/attackiq tui --help`
- `.venv/bin/attackiq export assessments --help`
- `.venv/bin/attackiq backup configs --help`

## Validation Results

| Check | Result | Notes |
| --- | --- | --- |
| `.venv/bin/attackiq --help` | Pass | Top-level command tree is consistent with current docs. |
| `.venv/bin/attackiq backup configs --help` | Pass | Help shows required output directory, bounded pagination, endpoint catalog, TLS, timeout, and tenant alias options. |
| `python3 scripts/check_dependency_constraints.py` | Pass | Dependency metadata and constraints are aligned. |
| `python3 scripts/check_release_governance.py` | Pass | Release governance OK. |
| `python3 scripts/check_public_safety.py --skip-wheel` | Pass | Tracked source scan OK. |
| `python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Pass | Public mirror dry run OK for `HEAD`; manifest reported public target `hubert-cumberdale/attackiq-cli`. |
| `.venv/bin/python scripts/quality_gate.py` | Pass | Includes public safety, mirror dry run, MCP gates, Ruff, mypy, 494 pytest tests, doc links, and MkDocs build. |
| `python3 scripts/check_doc_links.py` | Pass | All referenced files exist. |
| `python3 scripts/render_deep_dives.py --check` | Pass | Deep-dive docs are up to date. |
| `python3 scripts/verify_deep_dives.py` | Pass | Deep-dive verification passed. |
| `.venv/bin/pip-audit` | Pass with expected skip | No known vulnerabilities found; local `attackiq-cli` package skipped because it is not on PyPI. |
| `.venv/bin/pip-audit -r constraints.txt --no-deps` | Pass | No known vulnerabilities found in pinned constraints. |

## Enterprise Delivery Simulation

The no-Artifactory path was validated locally with public release tag `v0.1.24`.

| Step | Result | Evidence |
| --- | --- | --- |
| Build package from public tag | Pass | `scripts/build_enterprise_package.py --source-ref v0.1.24` built `attackiq_cli-0.1.24-py3-none-any.whl` from public source commit `7cdd6b30366ca5f5b8f13f62357137ed21cea4a8`. |
| Verify package directory | Pass | `scripts/verify_enterprise_package.py <package-dir> --require-constraints` verified checksums, manifest, provenance, and install constraints. |
| Generate Artifactory evidence | Pass | Placeholder-safe `https://artifactory.example.com/artifactory` URL and relative repository path were accepted; evidence recorded five promotion files. |
| Generate signing evidence | Pass | Credential-free signing evidence recorded six signing subjects. |
| Verify generated enterprise evidence | Pass | `scripts/verify_enterprise_evidence.py <package-dir> --require-artifactory --require-signing` cross-checked package, Artifactory evidence, and signing evidence. |
| Populate local wheelhouse | Pass | `pip download` captured the release wheel and constrained runtime dependencies into a local wheelhouse. |
| Install from local wheelhouse | Pass | A fresh venv installed `attackiq-cli==0.1.24` with `--no-index --find-links` and constraints, then `attackiq --version` and `attackiq config validate` succeeded. |

This validates the offline enterprise handoff that can be performed without Artifactory access.
Real upload/download verification, registry authentication, signing execution, attestation
publication, trust-root validation, repository permissions, and retention controls remain
operator-owned external validation.

## Architecture Findings

### Medium - CI and Local Quality Gate Drift

File references:

- `.github/workflows/ci.yml:34`
- `.github/workflows/ci.yml:35`
- `scripts/quality_gate.py:39`
- `scripts/quality_gate.py:52`

Detail:

- The local quality gate lints `scripts/verify_enterprise_evidence.py`; CI does not.
- The local quality gate runs the AIQ Assist MCP provider contract and fixture gates; CI does not
  run matching steps in the main test matrix.
- Local validation still passed, but CI can miss regressions in scripts and contracts that the
  release checklist treats as standard local evidence.

Risk:

- Pull requests can pass CI while failing the documented local release gate.
- Enterprise evidence verification and MCP contract maturity can drift unnoticed until a release
  operator runs local checks.

Recommendation:

- Make CI reuse `scripts/quality_gate.py --no-mkdocs` or share a generated command list with
  `scripts/quality_gate.py`.
- At minimum, add CI steps for the AIQ Assist MCP gates and add
  `scripts/verify_enterprise_evidence.py` to the workflow Ruff target list.

### Medium - Large Mixed-Responsibility Modules Increase Regression Risk

File references:

- `src/attackiq_cli/cli.py` has 5,749 lines.
- `src/attackiq_cli/tui.py` has 6,151 lines.
- `src/attackiq_cli/services.py` has 2,690 lines.
- `src/attackiq_cli/scenario_wizard.py` has 2,469 lines.
- `src/attackiq_cli/backup.py` has 866 lines.

Detail:

- The current boundaries are understandable and documented, but command definitions, output
  helpers, dry-run/apply orchestration, TUI state, provider caching, service-layer query builders,
  and backup domain handling are concentrated in a few files.
- This is acceptable for the current release because tests are broad and the security controls are
  centralized, but continued wrapper and TUI expansion will make review harder.

Risk:

- Small feature additions can touch unrelated command families.
- Reviewers must reason about large files when validating redaction, dry-run/apply, and output
  behavior.

Recommendation:

- Treat decomposition as a planned roadmap track, not an emergency rewrite.
- Extract focused service submodules and shared dry-run/output helpers before adding broad new
  command families.
- Keep `tui.py` read-only and move reusable provider/cache/query behavior behind service-layer
  contracts.

### Low-Medium - Enterprise Artifactory Boundary Is Documented But Externally Dependent

File references:

- `docs/ARTIFACTORY_DELIVERY.md:3`
- `docs/ARTIFACTORY_DELIVERY.md:71`
- `docs/ARTIFACTORY_DELIVERY.md:89`

Detail:

- The repo correctly does not accept registry credentials, upload to Artifactory, sign artifacts,
  or verify enterprise trust roots.
- Offline package, Artifactory evidence, signing evidence, and evidence-verifier checks passed.
- The current docs clearly mark the external operator-owned boundary, but production acceptance
  still needs an operator-run upload/download/install/trust-root record.

Risk:

- A release can be locally mature while the enterprise packaging workflow remains unproven in a
  specific customer's Artifactory and signing environment.

Recommendation:

- Preserve the credential-free boundary.
- Add a standard operator evidence template for external Artifactory download verification,
  signature verification, attestation verification, and trust-root checks.

### Low-Medium - Supply Chain Controls Are Good But Not Yet Strong Enterprise Provenance

File references:

- `constraints.txt`
- `scripts/build_enterprise_package.py`
- `scripts/package_provenance.py`
- `scripts/verify_enterprise_package.py`

Detail:

- Runtime and dev dependency versions are pinned in `constraints.txt`.
- `pip-audit` passed for the installed environment and constrained requirements.
- Enterprise package artifacts include constraints, checksums, promotion manifest, and package
  provenance.
- Constraints are not hash-pinned, the package does not currently emit a CycloneDX/SPDX SBOM as a
  release artifact, and CI does not run a dedicated secret-scanning gate.

Risk:

- Enterprise consumers may need stronger evidence for package provenance, dependency integrity,
  and accidental secret leakage than the current baseline provides.

Recommendation:

- Add generated SBOM output to enterprise package artifacts.
- Add a hash-pinned constraints option or release artifact.
- Add secret scanning to CI using an allowlisted config.
- Expand least-privilege token guidance for GitHub release and Artifactory handoff operators.

### Low - Backup Domain Expansion Needs Deliberate Intake

File references:

- `src/attackiq_cli/backup.py:21`
- `src/attackiq_cli/backup.py:174`
- `src/attackiq_cli/backup.py:216`
- `src/attackiq_cli/backup.py:642`
- `src/attackiq_cli/backup.py:680`

Detail:

- `attackiq backup configs` defaults to integrations, source types, and detection rules.
- Endpoint catalog entries reject unsupported/write-like classifications and require
  `needs-redaction` entries to declare sensitive fields.
- Redaction behavior is broad and fixture-backed.

Risk:

- Backup-domain growth could create tenant-data leakage or restore/apply confusion if intake
  shortcuts are allowed.

Recommendation:

- Continue expanding backup domains only through reviewed endpoint catalogs, fixtures, and
  redaction tests.
- Keep restore/apply behavior out of the first backup workflow.

### Low - AIQ Assist MCP Contract Remains Pre-Implementation

File references:

- `docs/AIQ_ASSIST_MCP_CONTRACT.md`
- `scripts/check_aiq_assist_mcp_contract.py`
- `scripts/check_aiq_assist_mcp_fixtures.py`

Detail:

- The contract is intentionally `v0` and blocks user-facing CLI/TUI consumption until the provider
  contract source is documented.
- Synthetic fixture gates passed locally.

Risk:

- Future MCP work can outpace the provider contract if roadmap tracking is not explicit.

Recommendation:

- Keep MCP work in contract and fixture maturity until provider ownership, auth modes, timeout
  behavior, and failure redaction are settled.

## Security Posture

Strong controls observed:

- `AttackIQClient` requires a positive timeout and creates `httpx.Client` with explicit timeout and
  TLS verification settings.
- `services.build_client` centralizes per-command timeout validation and `--insecure` handling.
- `client.redact_headers` redacts authorization, proxy authorization, cookies, API keys, tokens,
  and JWT-shaped header names.
- Backup redaction covers sensitive keys, signed URLs, bearer/token/basic values, JWT-shaped
  strings, and private-key material.
- Backup output is refused inside the git worktree when detectable and files/directories are
  permission-restricted.
- Mutation commands remain dry-run/apply gated, and the TUI remains read-only.
- Public-safety scans block known private references, local workstation paths, and disallowed wheel
  contents.

Residual risks:

- Some broad exception handling remains in TUI/export/network defensive paths and should be kept
  narrow when files are decomposed.
- Hash-pinned dependencies and generated SBOMs are future hardening items.
- Secret scanning is not currently part of CI.

## Documentation Drift

Observed docs are generally aligned with help output and governance boundaries.

Drift or follow-up needed:

- Document the no-Artifactory local wheelhouse install simulation as accepted validation evidence.
- Explicitly track CI/local quality-gate parity in production readiness and roadmap docs.
- Make the architecture standards name the current oversized modules as planned refactor targets.
- Keep Artifactory docs as an external operator boundary, not a repo-owned CI responsibility.

No raw tenant payloads, private host data, browser artifacts, or credentials were found in the
reviewed public docs.

## Roadmap Deltas

Priority order:

1. Quality-gate parity: align GitHub Actions with `scripts/quality_gate.py` and keep future script
   additions in one source of truth.
2. Architecture decomposition: split `src/attackiq_cli/cli.py`, `src/attackiq_cli/tui.py`,
   `src/attackiq_cli/services.py`, `src/attackiq_cli/scenario_wizard.py`, and
   `src/attackiq_cli/backup.py` incrementally along existing boundaries.
3. Enterprise install simulation: keep the public-tag package build, evidence verification, and
   local wheelhouse install simulation as standard release evidence.
4. Backup-domain expansion: grow through sanitized endpoint catalogs, fixtures, redaction tests,
   and no restore/apply path.
5. AIQ Assist MCP contract maturity: keep provider-source, fixtures, auth, timeout, and failure
   mode work ahead of CLI/TUI commands.
6. TUI dry-run previews: design read-only call-plan previews without apply-mode execution.
7. Wrapper expansion: add one read-only wrapper family at a time with service-level tests first.
8. Supply-chain hardening: SBOM export, hash-pinned constraints, secret scanning, artifact signing
   guidance, trust-root verification guidance, and least-privilege token docs.

Candidate future features, not approved implementation:

- SBOM export in enterprise package artifacts.
- Richer backup domain catalog coverage.
- Package provenance diffing between public tag, enterprise package, and downloaded artifact.
- Local release-audit command that wraps the full validation suite and records public-safe evidence.
- Issue-backed roadmap tracking with one GitHub issue per roadmap milestone.

## Issue Milestones

Created one source-repository GitHub issue per milestone:

- Quality gate parity and CI release governance.
- Architecture decomposition.
- Enterprise package and no-Artifactory install simulation.
- Backup-domain maturity.
- AIQ Assist MCP contract maturity.
- TUI dry-run previews.
- Read-only wrapper expansion.
- Supply-chain and provenance hardening.

Use existing labels only: `governance`, `documentation`, `enhancement`, `release`, or `bug`.

## Conclusion

The project is mature enough for the documented production-ready `v0.1.24` boundary and the
offline enterprise handoff that does not require Artifactory access. The next maturity step is to
reduce governance drift and review cost: make CI match local gates, split large modules
incrementally, preserve the no-credential Artifactory boundary, and turn the roadmap deltas into
tracked issues.
