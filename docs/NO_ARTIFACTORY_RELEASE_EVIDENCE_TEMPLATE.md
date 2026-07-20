# No-Artifactory Release Evidence Template

Use this template when validating an enterprise package handoff without direct Artifactory access.
The completed record belongs in the approved enterprise release system or a local evidence
directory outside git. Keep this repository limited to placeholder-safe examples.

The current wrapper evaluation is recorded in `docs/RELEASE_AUDIT_WRAPPER_EVALUATION.md`. It keeps
this template plus the existing individual validation scripts as the repository-owned evidence
standard until a future wrapper meets the documented redaction and output-location criteria.

## Public-Safe Boundary

Allowed in repo-owned examples:

- public release tag and public commit SHA
- package artifact filenames, sizes, and SHA256 values
- placeholder Artifactory URL and repository path
- placeholder signing profile name
- pass/fail command results without operator names or workstation paths

Do not record in this repository:

- registry credentials, signing keys, tokens, cookies, bearer headers, or `.netrc` content
- private Artifactory coordinates, internal package indexes, trust-root paths, or certificates
- operator names, change-ticket identifiers, tenant names, or internal audit-log URLs
- raw tenant responses, screenshots, generated package directories, wheelhouses, or local venvs

## Release Identity

| Field | Value |
| --- | --- |
| Release tag | `vX.Y.Z` |
| Public source repository | `https://github.com/hubert-cumberdale/attackiq-cli` |
| Public source commit | `<public-tag-commit-sha>` |
| Package version | `X.Y.Z` |
| Evidence date UTC | `<YYYY-MM-DDTHH:MM:SSZ>` |
| Evidence location | `<approved external release record or local path outside git>` |

## Repository-Owned Command Evidence

Record command status as `pass`, `fail`, or `not in scope`. Keep paths placeholder-safe when the
record may be shared back into repository docs.

| Step | Command | Status | Public-safe notes |
| --- | --- | --- | --- |
| Build enterprise package | `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <package-dir-outside-git>` | `<status>` | `<source ref, package dir outside git>` |
| Verify package | `python3 scripts/verify_enterprise_package.py <package-dir-outside-git> --require-constraints` | `<status>` | `<manifest/checksum/SBOM/dependency-integrity/provenance result>` |
| Generate Artifactory promotion evidence | `python3 scripts/build_artifactory_promotion_evidence.py <package-dir-outside-git> --artifactory-url https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local --output <package-dir-outside-git>/ARTIFACTORY_PROMOTION_EVIDENCE.json` | `<status>` | `<promotion file count and credential-free URL/path validation>` |
| Generate signing/attestation evidence | `python3 scripts/build_signing_attestation_evidence.py <package-dir-outside-git> --signing-profile enterprise-release --output <package-dir-outside-git>/SIGNING_ATTESTATION_EVIDENCE.json` | `<status>` | `<signing subject count and no-key boundary>` |
| Verify generated evidence | `python3 scripts/verify_enterprise_evidence.py <package-dir-outside-git> --require-artifactory --require-signing` | `<status>` | `<package/evidence cross-check summary>` |
| Build local wheelhouse | `python -m pip download --dest <package-dir-outside-git>/local-wheelhouse -c <package-dir-outside-git>/constraints.txt <package-dir-outside-git>/attackiq_cli-X.Y.Z-py3-none-any.whl` | `<status>` | `<dependency availability summary>` |
| Install without Artifactory | `<install-venv>/bin/python -m pip install --no-index --find-links <package-dir-outside-git>/local-wheelhouse -c <package-dir-outside-git>/constraints.txt attackiq-cli==X.Y.Z` | `<status>` | `<offline install summary>` |
| CLI version smoke | `<install-venv>/bin/attackiq --version` | `<status>` | `attackiq-cli version X.Y.Z` |
| Config smoke | `<install-venv>/bin/attackiq config validate` | `<status>` | `<Config OK or redacted failure>` |
| Dependency smoke | `<install-venv>/bin/python -m pip check` | `<status>` | `<no broken requirements or redacted failure>` |

## Artifact Digest Evidence

| Artifact | Expected filename | SHA256 | Size bytes | Status |
| --- | --- | --- | --- | --- |
| Wheel | `attackiq_cli-X.Y.Z-py3-none-any.whl` | `<sha256>` | `<bytes>` | `<status>` |
| Constraints | `constraints.txt` | `<sha256>` | `<bytes>` | `<status>` |
| Checksums | `SHA256SUMS` | `<sha256>` | `<bytes>` | `<status>` |
| Promotion manifest | `ENTERPRISE_PROMOTION_MANIFEST.json` | `<sha256>` | `<bytes>` | `<status>` |
| SBOM | `ENTERPRISE_PACKAGE_SBOM.spdx.json` | `<sha256>` | `<bytes>` | `<status>` |
| Dependency integrity | `ENTERPRISE_DEPENDENCY_INTEGRITY.json` | `<sha256>` | `<bytes>` | `<status>` |
| Package provenance | `ENTERPRISE_PACKAGE_PROVENANCE.json` | `<sha256>` | `<bytes>` | `<status>` |
| Artifactory evidence | `ARTIFACTORY_PROMOTION_EVIDENCE.json` | `<sha256>` | `<bytes>` | `<status>` |
| Signing evidence | `SIGNING_ATTESTATION_EVIDENCE.json` | `<sha256>` | `<bytes>` | `<status>` |

## External Signing And Attestation Evidence

Record real values only in the approved enterprise release system. Repo-owned copies should keep
placeholder values or public-safe summaries.

| Evidence group | Required fields | External record value |
| --- | --- | --- |
| Signature verification | `subject_filename`, `subject_sha256`, `signature_file`, `signature_sha256`, `signing_profile`, `signing_identity`, `verification_command`, `verification_status`, `verified_utc`, `external_evidence_uri` | `<enterprise release record>` |
| Attestation verification | `subject_filename`, `subject_sha256`, `attestation_file`, `attestation_sha256`, `predicate_type`, `predicate_fields_verified`, `source_ref`, `source_commit`, `package_version`, `provenance_reference`, `artifactory_target_path`, `verification_command`, `verification_status`, `verified_utc`, `external_evidence_uri` | `<enterprise release record>` |
| Trust-root verification | `trust_root_identifier`, `trust_policy_identifier`, `trust_root_version_or_digest`, `verification_tool`, `verification_command`, `verification_status`, `verified_subject_sha256_values`, `verified_utc`, `external_evidence_uri` | `<enterprise release record>` |

Do not copy private keys, signing tokens, registry credentials, certificates, private trust-root
paths, operator names, change-ticket identifiers, or internal audit-log URLs into this repository.

## External Operator Checklist

These controls remain outside repo-owned automation. Record the real values only in the approved
enterprise release system.

| External control | Status | Private evidence location |
| --- | --- | --- |
| Artifactory upload completed through approved workflow | `<status>` | `<enterprise release record>` |
| Downloaded Artifactory package directory passed offline verification | `<status>` | `<enterprise release record>` |
| Package repository token scope and expiry reviewed | `<status>` | `<enterprise release record>` |
| Detached signature verification completed | `<status>` | `<enterprise release record>` |
| Attestation verification completed | `<status>` | `<enterprise release record>` |
| Trust-root identifier and verified subject digests recorded | `<status>` | `<enterprise release record>` |
| Retention policy for generated package/evidence directories approved | `<status>` | `<enterprise release record>` |

## Post-Download Package Checklist

Use `docs/POST_DOWNLOAD_PACKAGE_EVIDENCE_CHECKLIST.md` when a downloaded package directory or local
handoff package directory is ready for final acceptance. The checklist cross-checks wheel,
constraints, SBOM, dependency integrity, provenance, signatures, attestations, trust-root
verification, and install smoke evidence against one release record.

## Final No-Artifactory Decision

- Repository-owned no-Artifactory evidence status: `<accepted | rejected | not in scope>`.
- Blocking failures: `<none or public-safe summary>`.
- External enterprise controls still required before production promotion:
  `<Artifactory upload/download | signing | attestation | trust-root | permissions | retention>`.
