# Post-Download Package Evidence Checklist

Use this checklist after an enterprise package is downloaded from Artifactory or another approved
package repository. It also applies to a no-Artifactory handoff when the downloaded directory is
represented by a clean local package directory outside git.

Keep real signing identities, certificates, private trust-root paths, operator names, change-ticket
identifiers, internal URLs, and audit-log links in the approved enterprise release system. Repository
docs may record only placeholder values or public-safe pass/fail summaries.

## Inputs

| Field | Value |
| --- | --- |
| Release tag | `vX.Y.Z` |
| Public source commit | `<public-tag-commit-sha>` |
| Package version | `X.Y.Z` |
| Downloaded package directory | `<download-dir-outside-git>` |
| External evidence record | `<enterprise release record>` |
| Evidence date UTC | `<YYYY-MM-DDTHH:MM:SSZ>` |

## Package Artifact Cross-Check

Run local package verification first:

```bash
python3 scripts/verify_enterprise_package.py <download-dir-outside-git> --require-constraints
python3 scripts/verify_enterprise_evidence.py \
  <download-dir-outside-git> \
  --require-artifactory \
  --require-signing
```

Record the cross-check status for each expected artifact:

| Artifact | Expected record | Cross-check | Status |
| --- | --- | --- | --- |
| Wheel | `ENTERPRISE_PROMOTION_MANIFEST.json`, `SHA256SUMS` | Filename, size, SHA256, wheel metadata, public-safety verification | `<status>` |
| Constraints | `constraints.txt`, manifest `constraints_file`, `SHA256SUMS` | Exact SHA256 and install constraint presence | `<status>` |
| SBOM | `ENTERPRISE_PACKAGE_SBOM.spdx.json`, manifest `sbom_file`, `SHA256SUMS` | Exact SHA256 and package/dependency inventory presence | `<status>` |
| Dependency integrity | `ENTERPRISE_DEPENDENCY_INTEGRITY.json`, manifest `dependency_integrity_file`, `SHA256SUMS` | Exact SHA256 and constraints digest match | `<status>` |
| Package provenance | `ENTERPRISE_PACKAGE_PROVENANCE.json`, manifest `provenance_file`, `SHA256SUMS` | Source ref, source commit, package version, wheel digest | `<status>` |
| Artifactory evidence | `ARTIFACTORY_PROMOTION_EVIDENCE.json` when in scope | Target paths, upload records, post-upload checks, consumer install checks | `<status>` |
| Signing evidence | `SIGNING_ATTESTATION_EVIDENCE.json` when in scope | Signing subjects, expected outputs, external evidence field groups | `<status>` |

If Artifactory or signing evidence is intentionally out of scope, mark the status as `not in scope`
and record the reason in the external release record.

## Signature And Attestation Cross-Check

Use the `external_evidence_fields` names from `SIGNING_ATTESTATION_EVIDENCE.json` for the external
record. Do not copy private values into repository-owned docs.

| Check | Required external evidence | Status |
| --- | --- | --- |
| Detached signatures | `subject_filename`, `subject_sha256`, `signature_file`, `signature_sha256`, `signing_profile`, `signing_identity`, `verification_command`, `verification_status`, `verified_utc`, `external_evidence_uri` | `<status>` |
| Attestations | `subject_filename`, `subject_sha256`, `attestation_file`, `attestation_sha256`, `predicate_type`, `predicate_fields_verified`, `source_ref`, `source_commit`, `package_version`, `provenance_reference`, `artifactory_target_path`, `verification_command`, `verification_status`, `verified_utc`, `external_evidence_uri` | `<status>` |
| Trust root | `trust_root_identifier`, `trust_policy_identifier`, `trust_root_version_or_digest`, `verification_tool`, `verification_command`, `verification_status`, `verified_subject_sha256_values`, `verified_utc`, `external_evidence_uri` | `<status>` |

Every verified signature and attestation must bind the same subject filename and SHA256 recorded in
the downloaded package directory.

## Install Smoke Evidence

Install from the downloaded package set or approved package index with the downloaded
`constraints.txt`:

```bash
python -m venv <install-venv>
<install-venv>/bin/python -m pip install --upgrade pip
<install-venv>/bin/python -m pip install \
  -c <download-dir-outside-git>/constraints.txt \
  --no-index \
  --find-links <download-dir-outside-git>/local-wheelhouse \
  attackiq-cli==X.Y.Z
<install-venv>/bin/attackiq --version
<install-venv>/bin/attackiq config validate
<install-venv>/bin/python -m pip check
```

For an Artifactory-backed install, replace `--no-index --find-links` with the approved package
index configuration. Do not place package-index credentials, `.netrc` entries, pip config files, or
signed URLs in repository-owned records.

| Smoke check | Expected result | Status |
| --- | --- | --- |
| Wheel install with downloaded constraints | `attackiq-cli==X.Y.Z` installs without dependency conflicts | `<status>` |
| CLI version | `attackiq-cli version X.Y.Z` | `<status>` |
| Config validation | `Config OK` or redacted failure summary | `<status>` |
| Dependency check | `No broken requirements found` or redacted failure summary | `<status>` |

## Final Evidence Decision

- Post-download package evidence status: `<accepted | rejected | not in scope>`.
- Blocking failures: `<none or public-safe summary>`.
- External records retained outside git:
  `<download verification | signatures | attestations | trust root | install smoke | retention>`.
