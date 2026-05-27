# Artifactory Delivery

This workflow prepares enterprise promotion evidence for an already generated package directory.
It does not upload files, accept registry credentials, sign artifacts, or create registry
attestations.

## Inputs

Start from a verified enterprise package directory built from a public release tag:

```bash
python3 scripts/build_enterprise_package.py \
  --source-ref v0.1.22 \
  --output-dir /tmp/attackiq-cli-enterprise-package-v0.1.22
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-enterprise-package-v0.1.22 --require-constraints
```

The package directory contains:

- `attackiq_cli-<version>-py3-none-any.whl`
- `constraints.txt`
- `SHA256SUMS`
- `ENTERPRISE_PROMOTION_MANIFEST.json`
- `ENTERPRISE_PACKAGE_PROVENANCE.json`

## Promotion Evidence

Generate a public-safe promotion evidence file outside the source repository:

```bash
python3 scripts/build_artifactory_promotion_evidence.py \
  /tmp/attackiq-cli-enterprise-package-v0.1.22 \
  --artifactory-url https://artifactory.example.com/artifactory \
  --repository-path api/pypi/attackiq-cli-local \
  --output /tmp/attackiq-cli-enterprise-package-v0.1.22/ARTIFACTORY_PROMOTION_EVIDENCE.json
```

The evidence generator:

- re-runs offline package verification before writing evidence
- refuses Artifactory URLs with embedded credentials
- requires HTTPS Artifactory URLs
- refuses query strings, fragments, absolute repository paths, and parent path traversal
- records upload filenames, including `constraints.txt`, SHA256 values, sizes, and target paths
- records post-upload verification and consumer install checks

Do not commit the evidence file if it contains internal Artifactory coordinates.

## Signing And Attestation Evidence

If signing or registry attestation is required, generate signing evidence after Artifactory
promotion evidence is available:

```bash
python3 scripts/build_signing_attestation_evidence.py \
  /tmp/attackiq-cli-enterprise-package-v0.1.22 \
  --signing-profile enterprise-release \
  --output /tmp/attackiq-cli-enterprise-package-v0.1.22/SIGNING_ATTESTATION_EVIDENCE.json
```

This records signing subjects, SHA256 values, expected detached signature filenames, expected
attestation filenames, and predicate requirements. It does not accept signing keys or perform
signing. Keep generated signing evidence in the enterprise release record if it contains internal
signing profile names or repository coordinates.

## Upload Boundary

Upload these files through the approved enterprise Artifactory workflow:

- wheel file
- `constraints.txt`
- `SHA256SUMS`
- `ENTERPRISE_PROMOTION_MANIFEST.json`
- `ENTERPRISE_PACKAGE_PROVENANCE.json`
- optional `ARTIFACTORY_PROMOTION_EVIDENCE.json` in the change ticket or internal release record

Keep Artifactory credentials in enterprise secret storage, environment variables, or approved
package-manager configuration. Do not place tokens in repository files, command history, release
notes, URLs, or logs.

Artifact signing, registry attestation, repository permissions, retention policy, and promotion
approval remain enterprise-owned controls.

## Post-Upload Verification

Download the uploaded files into a clean directory outside git and repeat the offline verification:

```bash
python3 scripts/verify_enterprise_package.py /tmp/attackiq-cli-artifactory-download-v0.1.22 --require-constraints
```

Then verify installation from the enterprise package repository:

```bash
python -m venv .venv-artifactory-smoke
source .venv-artifactory-smoke/bin/activate
python -m pip install -c constraints.txt --upgrade pip
python -m pip install -c constraints.txt \
  --index-url <artifactory-python-index-url> \
  attackiq-cli==0.1.22
attackiq --version
attackiq config validate
```

Record only public-safe evidence in this repository. Internal Artifactory URLs, change tickets,
operator names, and registry audit logs should stay in the enterprise release system.
