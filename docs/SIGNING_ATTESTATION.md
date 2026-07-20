# Signing And Attestation

This workflow prepares public-safe signing and attestation evidence for a verified enterprise
package directory. It does not sign files, accept signing keys, upload artifacts, or verify
enterprise trust roots.

## Inputs

Start from a verified package directory. If Artifactory promotion is in scope, generate the
Artifactory promotion evidence first so signing subjects include target paths:

```bash
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-vX.Y.Z --require-constraints
python3 scripts/build_artifactory_promotion_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --artifactory-url https://artifactory.example.com/artifactory \
  --repository-path api/pypi/attackiq-cli-local \
  --output /tmp/attackiq-cli-enterprise-package-vX.Y.Z/ARTIFACTORY_PROMOTION_EVIDENCE.json
```

## Evidence Generation

Generate signing and attestation evidence outside the source repository:

```bash
python3 scripts/build_signing_attestation_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --signing-profile enterprise-release \
  --output /tmp/attackiq-cli-enterprise-package-vX.Y.Z/SIGNING_ATTESTATION_EVIDENCE.json
python3 scripts/verify_enterprise_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --require-artifactory \
  --require-signing
```

The evidence generator:

- re-runs offline package verification before writing evidence
- refuses signing profile values that look like URLs or secret-like material
- records each signing subject filename, type, size, SHA256, and Artifactory target when available
- records expected detached signature and attestation filenames
- records required predicate fields for enterprise attestations
- records standardized external evidence field names for signature, attestation, and trust-root
  verification
- records pre-signing and post-signing verification checks
- cross-checks generated evidence against local package artifacts with the evidence verifier

Do not commit the evidence file if it contains internal signing profile names, Artifactory
coordinates, change-ticket data, or enterprise trust-root details.

## Standardized External Evidence Fields

`SIGNING_ATTESTATION_EVIDENCE.json` includes an `external_evidence_fields` section. It standardizes
the names operators should use in the approved enterprise release record, but it does not populate
private values in repository-owned files.

Use these fields for detached signature verification:

- `subject_filename`
- `subject_sha256`
- `signature_file`
- `signature_sha256`
- `signing_profile`
- `signing_identity`
- `verification_command`
- `verification_status`
- `verified_utc`
- `external_evidence_uri`

Use these fields for attestation verification:

- `subject_filename`
- `subject_sha256`
- `attestation_file`
- `attestation_sha256`
- `predicate_type`
- `predicate_fields_verified`
- `source_ref`
- `source_commit`
- `package_version`
- `provenance_reference`
- `artifactory_target_path`
- `verification_command`
- `verification_status`
- `verified_utc`
- `external_evidence_uri`

Use these fields for trust-root verification:

- `trust_root_identifier`
- `trust_policy_identifier`
- `trust_root_version_or_digest`
- `verification_tool`
- `verification_command`
- `verification_status`
- `verified_subject_sha256_values`
- `verified_utc`
- `external_evidence_uri`

The verifier requires the field groups above. Real signing identities, certificates, trust-root
paths, operator names, change-ticket identifiers, and audit-log URLs belong in the enterprise
release system, not in repo-owned examples or public release notes.

## Signing Boundary

Enterprise operators own signing execution. Keep private keys, certificates, signing credentials,
registry credentials, trust-root configuration, and signing logs in the approved enterprise signing
system.

Recommended subject coverage:

- wheel file
- `constraints.txt`
- `SHA256SUMS`
- `ENTERPRISE_PROMOTION_MANIFEST.json`
- `ENTERPRISE_PACKAGE_PROVENANCE.json`
- `ARTIFACTORY_PROMOTION_EVIDENCE.json` when generated

Detached signatures and attestations should bind the exact filename and SHA256 values from
`SIGNING_ATTESTATION_EVIDENCE.json`.

## Post-Signing Verification

Before promotion completion:

```bash
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-vX.Y.Z --require-constraints
python3 scripts/verify_enterprise_evidence.py \
  /tmp/attackiq-cli-enterprise-package-vX.Y.Z \
  --require-artifactory \
  --require-signing
```

Then use the approved enterprise signing tool to verify:

- every expected signature file exists
- every expected attestation file exists
- every attestation binds the expected subject filename and SHA256
- the signing identity/profile matches the approved release policy
- uploaded artifacts downloaded from Artifactory still pass package verification

Record only public-safe summaries in this repository. Internal signing logs, trust-root details,
operator names, and registry audit logs should stay in the enterprise release system.

After downloading the promoted package set, use
`docs/POST_DOWNLOAD_PACKAGE_EVIDENCE_CHECKLIST.md` to cross-check package artifacts, detached
signatures, attestations, trust-root verification, and install smoke evidence against the same
subject filenames and SHA256 values.
