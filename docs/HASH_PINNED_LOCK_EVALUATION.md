# Hash-Pinned Lock Evaluation

This note records the #61 follow-up decision on whether to add hash-pinned lock or constraints
generation as a stricter alternative or complement to the current dependency-integrity record.

## Current Standard

The current enterprise package evidence uses:

- exact version pins in `constraints.txt`
- `scripts/check_dependency_constraints.py` to prove direct runtime, dev, and release-audit
  dependencies are covered by exact pins
- `ENTERPRISE_DEPENDENCY_INTEGRITY.json` to record the constraints file SHA256, per-pin normalized
  dependency records, per-line SHA256 values, and pinned dependency count
- `SHA256SUMS`, `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_SBOM.spdx.json`, and
  `ENTERPRISE_PACKAGE_PROVENANCE.json` to bind the built package artifact set
- `scripts/verify_enterprise_package.py --require-constraints` and
  `scripts/verify_enterprise_evidence.py` to cross-check generated package and evidence records

This is stronger than unpinned dependency metadata because it fails closed on missing pins,
constraint drift, package-manifest drift, SBOM/dependency-integrity drift, and package artifact
digest drift. It does not pin every downloaded distribution artifact hash in pip's
`--require-hashes` format.

## Hash-Pinned Option

A hash-pinned constraints or lock artifact would add pip-compatible `--hash=sha256:<digest>` values
for every resolved dependency artifact. Candidate approaches:

- generate a dedicated runtime lock such as `requirements-hashes.txt`
- generate a hash-pinned release constraints artifact alongside `constraints.txt`
- generate a wheelhouse manifest that binds each downloaded dependency filename and SHA256

Any approach must prove:

- reproducible generation from the public release tag
- Python 3.10, 3.11, and 3.12 install compatibility
- marker and platform coverage for transitive dependencies
- compatibility with editable/dev installs staying out of release evidence
- `pip-audit` compatibility for the locked runtime set
- no private index URLs, credentials, local paths, or trust-root material in repo-owned files
- offline verification against the generated package directory before release evidence is accepted

## Decision

Keep `constraints.txt` plus `ENTERPRISE_DEPENDENCY_INTEGRITY.json` as the current release standard.
Do not replace `constraints.txt` with pip `--require-hashes` constraints in this pass.

Rationale:

- the current record already binds exact pins and package evidence without introducing
  index-specific artifact hashes into the public repository
- pip hash constraints can become platform and marker sensitive, which raises maintenance risk
  unless the generation workflow is tested across the supported Python matrix
- a hash-pinned artifact is still useful, but it should be introduced as an additive release
  artifact after a focused prototype proves generation, audit, and install behavior

## Future Prototype Acceptance

A future implementation may add a hash-pinned runtime artifact only if it satisfies all of:

- generated from a clean public release tag, not the private working tree
- output stored in the enterprise package directory, not committed as a generated artifact
- verified by a script that checks every package filename, hash, marker, and install command
- tested with a clean install smoke on Python 3.10, 3.11, and 3.12
- documented as additive to `constraints.txt` until release operators approve replacement
- excluded from public release notes if it contains private index or trust-root references

## Validation

Decision-record validation:

```bash
python3 scripts/check_dependency_constraints.py
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
```
