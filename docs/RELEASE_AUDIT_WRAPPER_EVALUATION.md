# Release Audit Wrapper Evaluation

Decision date: 2026-06-02

## Decision

Do not add a repository-owned executing release-audit wrapper yet.

The current repository-owned no-Artifactory release evidence standard is
`docs/NO_ARTIFACTORY_RELEASE_EVIDENCE_TEMPLATE.md` plus the existing individual validation scripts.
Operators should continue to run and record the explicit commands for package build, package
verification, credential-free evidence generation, enterprise evidence verification, artifact
digests, and local wheelhouse install simulation.

## Rationale

The release evidence path already has focused scripts for the safety-critical pieces:

- `scripts/build_enterprise_package.py`
- `scripts/verify_enterprise_package.py`
- `scripts/build_artifactory_promotion_evidence.py`
- `scripts/build_signing_attestation_evidence.py`
- `scripts/verify_enterprise_evidence.py`
- `scripts/check_public_mirror.py`
- `scripts/quality_gate.py`

A wrapper that executes the full chain would cross several boundaries at once: package building
from a public tag, dependency download into a wheelhouse, fresh-venv installation, optional
promotion evidence generation, optional signing evidence generation, and local evidence capture.
Those steps can expose workstation paths, internal index configuration, private package
coordinates, operator identity, or redacted command output if the wrapper records too much by
default.

The existing template is safer for the current release line because it requires operators to keep
filled records outside git and records only public-safe command status, artifact digest, and
boundary summaries.

## Current Standard

Use the no-Artifactory evidence template when direct Artifactory access is unavailable. The
completed record belongs in an approved enterprise release system or a local evidence directory
outside git.

Repository-owned evidence may include:

- public release tag and public commit SHA
- package artifact filenames, sizes, and SHA256 values
- placeholder Artifactory URL and repository path
- placeholder signing profile name
- pass/fail command results without operator names or workstation paths

Repository-owned evidence must not include:

- registry credentials, signing keys, tokens, cookies, bearer headers, or `.netrc` content
- private Artifactory coordinates, internal package indexes, trust-root paths, or certificates
- operator names, change-ticket identifiers, tenant names, or internal audit-log URLs
- raw tenant responses, screenshots, generated package directories, wheelhouses, or local venvs

## Future Wrapper Criteria

A future release-audit wrapper can be considered as a new issue only if it stays inside this
repository-owned boundary.

Acceptance criteria for a future wrapper:

- Provides a dry-run or plan mode that lists the command sequence without executing it.
- Writes evidence only to an explicit output directory outside the repository and fails closed for
  repo-local output paths.
- Uses an allowlisted command manifest and argument-vector subprocess calls, not shell strings.
- Applies explicit command timeouts and records failures without leaking raw stdout/stderr.
- Records command names, versions, status, timestamps, artifact filenames, SHA256 values, and
  public-safe summaries only.
- Redacts local paths, private URLs, package indexes, tokens, operator names, and trust-root
  material before writing evidence.
- Accepts only placeholder Artifactory URLs and signing profile examples in repository-owned
  evidence examples.
- Never uploads to Artifactory, downloads from private package repositories, signs artifacts,
  publishes attestations, verifies enterprise trust roots, or runs live tenant commands.
- Has fixture-backed tests for output-location rejection, redaction, command manifest generation,
  failed-command recording, and digest capture.

Out of scope for a future wrapper:

- Release tagging or version bumping.
- Artifactory upload/download execution.
- Signing, attestation publication, or trust-root verification.
- Tenant live-smoke execution.
- Capturing private change tickets, operator names, workstation paths, package-index URLs, or
  raw command output.

Validation commands for a future wrapper PR:

```bash
python3 scripts/check_public_safety.py --skip-wheel
python3 scripts/check_secret_scan.py
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
pytest tests/test_<wrapper_name>.py
git diff --check
```
