# Signing And Attestation

This workflow prepares public-safe signing and attestation evidence for a verified enterprise
package directory. It does not sign files, accept signing keys, upload artifacts, or verify
enterprise trust roots.

## Inputs

Start from a verified package directory. If Artifactory promotion is in scope, generate the
Artifactory promotion evidence first so signing subjects include target paths:

```bash
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-v0.1.20
python3 scripts/build_artifactory_promotion_evidence.py \
  /tmp/attackiq-cli-enterprise-package-v0.1.20 \
  --artifactory-url https://artifactory.example.com/artifactory \
  --repository-path api/pypi/attackiq-cli-local \
  --output /tmp/attackiq-cli-enterprise-package-v0.1.20/ARTIFACTORY_PROMOTION_EVIDENCE.json
```

## Evidence Generation

Generate signing and attestation evidence outside the source repository:

```bash
python3 scripts/build_signing_attestation_evidence.py \
  /tmp/attackiq-cli-enterprise-package-v0.1.20 \
  --signing-profile enterprise-release \
  --output /tmp/attackiq-cli-enterprise-package-v0.1.20/SIGNING_ATTESTATION_EVIDENCE.json
```

The evidence generator:

- re-runs offline package verification before writing evidence
- refuses signing profile values that look like URLs or secret-like material
- records each signing subject filename, type, size, SHA256, and Artifactory target when available
- records expected detached signature and attestation filenames
- records required predicate fields for enterprise attestations
- records pre-signing and post-signing verification checks

Do not commit the evidence file if it contains internal signing profile names, Artifactory
coordinates, change-ticket data, or enterprise trust-root details.

## Signing Boundary

Enterprise operators own signing execution. Keep private keys, certificates, signing credentials,
registry credentials, trust-root configuration, and signing logs in the approved enterprise signing
system.

Recommended subject coverage:

- wheel file
- `SHA256SUMS`
- `ENTERPRISE_PROMOTION_MANIFEST.json`
- `ENTERPRISE_PACKAGE_PROVENANCE.json`
- `ARTIFACTORY_PROMOTION_EVIDENCE.json` when generated

Detached signatures and attestations should bind the exact filename and SHA256 values from
`SIGNING_ATTESTATION_EVIDENCE.json`.

## Post-Signing Verification

Before promotion completion:

```bash
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-v0.1.20
```

Then use the approved enterprise signing tool to verify:

- every expected signature file exists
- every expected attestation file exists
- every attestation binds the expected subject filename and SHA256
- the signing identity/profile matches the approved release policy
- uploaded artifacts downloaded from Artifactory still pass package verification

Record only public-safe summaries in this repository. Internal signing logs, trust-root details,
operator names, and registry audit logs should stay in the enterprise release system.
