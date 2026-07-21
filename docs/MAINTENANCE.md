# Maintenance

## Routine Tasks

- Run `python3 scripts/check_public_safety.py` before publication or package promotion.
- Run `python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel` during branch checks,
  then `python3 scripts/check_public_mirror.py --ref vX.Y.Z` from a clean worktree before public
  mirror publication.
- Run `python3 scripts/build_enterprise_package.py --source-ref vX.Y.Z --output-dir <dir>` after
  the public tag is available when enterprise package promotion is in scope.
- Run `python3 scripts/verify_enterprise_package.py <dir> --require-constraints` before package upload and after
  downloading the promoted package record when enterprise package promotion is in scope.
- Run `python3 scripts/build_artifactory_promotion_evidence.py <dir> --output <file>` after
  package verification when Artifactory promotion is in scope.
- Run `python3 scripts/build_signing_attestation_evidence.py <dir> --output <file>` after
  package and Artifactory evidence verification when signing or attestation is in scope.
- Run `python3 scripts/verify_enterprise_evidence.py <dir> --require-artifactory --require-signing`
  after generating both evidence files when Artifactory promotion and signing are in scope.
- Run `.venv/bin/python scripts/quality_gate.py` before release.
- Run `python3 scripts/check_dependency_constraints.py` before release.
- Run `python3 scripts/check_release_governance.py` before release and after changing release
  status docs.
- Run `python3 scripts/check_doc_links.py`, `python3 scripts/render_deep_dives.py --check`, and
  `python3 scripts/verify_deep_dives.py` before release.
- Run `pip-audit` against the installed release environment, plus dependency files when needed.
- Verify the release tag, `pyproject.toml`, `src/attackiq_cli/__init__.py`, `attackiq --version`,
  and `CHANGELOG.md` version heading agree before tagging.
- Review `openapi.yaml` updates and re-test CLI against the latest schema.
- Review GitHub Actions runtime deprecation annotations before each release and update
  official action majors before forced runtime transitions.

## Branching And Release Scheme

- Stable branch: `master`.
- Release branches: `release/v<major>.<minor>.<patch>` when a dedicated release branch is needed.
- Feature branches: `feature/cli-<short-scope>` and `feature/tui-<short-scope>`.
- Release tags: `v<major>.<minor>.<patch>`.
- Practice: merge feature branches into `master`, cut the release tag on `master`, then branch the
  next version from `master`.

## Spec Update Checklist

- Update `src/attackiq_cli/openapi.yaml`.
- Validate `attackiq spec list` and `attackiq spec show`.
- Run targeted read-only commands to confirm pagination and output.

## Security Checklist

- Verify TLS verification defaults remain enabled.
- Confirm redaction paths cover new headers and fields.
- Ensure new network calls set explicit timeouts.
- Confirm no private repository names, workstation paths, tenant data, or raw browser captures are
  tracked.

## Documentation Checklist

- Update `README.md` for user-visible commands.
- Update `docs/STATE.md` for release status, capabilities, or limitations.
- Update `docs/ARCHITECTURE.md` if modules or flows change.
- Record significant choices in `docs/DECISIONS.md`.

## v0.1.27 Release Evidence (2026-07-20)

- Release: `v0.1.27`.
- Private-source GitHub release: published for `v0.1.27` with no attached artifacts.
- Public GitHub release:
  `https://github.com/hubert-cumberdale/attackiq-cli/releases/tag/v0.1.27`.
- The public GitHub release is final and has zero attached artifacts.
- Source release commit: `6c26c502bfa16000fcb6bf8c4482b414f9bf8963`.
- Source annotated tag object: `aaff133d5ed0af7a525ab9a201e9a7570caf4c13`.
- Tag-time CI: run `29769671071` passed Python 3.10, 3.11, and 3.12 plus
  `release-hygiene` for the source release commit.
- Strict public mirror export: `PUBLICATION_MANIFEST.json` records source ref `v0.1.27`, source
  snapshot `git-archive`, package version `0.1.27`, tree SHA256
  `3a496ce22e988a5443dba7a2c0bc48f58953d00140f06e1d46431fc892346afc`, manifest SHA256
  `40b1d17372fe76883f5d989b60f58fe69d1132d5e5863c068d8918741bac13c6`, and no dirty-worktree
  allowance.
- Public lightweight tag and one-commit snapshot:
  `0af7861abebd0d5ef9f3443b389b54d5f30da3eb`; public safety passed from the snapshot. Public
  `main` initially remained at `ad46849452f5d63e5b84caf6df555d8120a095ae`, then was corrected
  with an exact-SHA force-with-lease on 2026-07-20. Public `main` and `v0.1.27` now resolve to the
  same snapshot, and corrective CI run `29778274916` passed Python 3.10, 3.11, and 3.12.
- Controlled non-production operational soak: public `v0.1.27` commit
  `0af7861abebd0d5ef9f3443b389b54d5f30da3eb` passed all 11 checks at
  `2026-07-20T20:06:03Z`: configuration validation, local spec discovery, five bounded read-only
  inventory calls, and four fake-ID dry-run call plans. No apply-mode operation ran.
- Enterprise wheel `attackiq_cli-0.1.27-py3-none-any.whl` SHA256:
  `94f9dca7686251cf6b6aa4bfe4bfffd4981c85b6e202caf347737bfac4154af3`.
- Enterprise install constraints SHA256:
  `f797149fab0deb8610c49cff7e21fa507f7c82703e1adce55b1c0812743c0db2`.
- Enterprise checksums file SHA256:
  `3ca51c9af76e0ac2c8f909a24ea185a1cd9936df63d090c0d5314bbe195f3af3`.
- Enterprise promotion manifest SHA256:
  `bea538478996bdc21eaf5cb4518cd508ce978e9847bacf1b4bae4776d23018af`.
- Enterprise SBOM SHA256:
  `78a3afe7e49f346f4db2675a595a8c2a4955b8df6b70008631f5289f9d621d59`.
- Enterprise dependency-integrity SHA256:
  `d1582772dc46525514d9601179e9bf6ff0841f2693715c58395dfcec17c22029`.
- Enterprise package provenance SHA256:
  `fe4fc82e7442f91fcc2ae44581bb2a6662321f62202ed8b889cd34159e49c98b`.
- Artifactory promotion evidence SHA256:
  `1b5883b2168516a48cfa0ff28df8d12feab3085b2d9322ab647b971db28cb55d`.
- Signing and attestation evidence SHA256:
  `b6adde4ee0b6e7a74284453ca3b13c68547d3d8cada7c73ef9556238b2e15fa9`.
- Enterprise package verification passed with required constraints and confirmed checksum, wheel,
  SBOM, dependency-integrity, provenance, and promotion-manifest agreement.
- Credential-free Artifactory evidence generation against the documented example HTTPS target
  passed with seven promotion records; signing evidence generation with profile
  `enterprise-release` passed with eight subjects; combined offline evidence verification passed.
- No-Artifactory install simulation: a fresh environment installed `attackiq-cli==0.1.27` from a
  local wheelhouse with `--no-index`, the promoted constraints, and no registry credentials;
  `attackiq --version` reported `attackiq-cli version 0.1.27`, `attackiq config validate` reported
  `Config OK`, and `python -m pip check` reported no broken requirements.
- Local release validation passed dependency constraints, release governance, public safety,
  secret scan, public mirror dry run, both dependency audits, Ruff, mypy, 761 pytest tests,
  documentation links, deep-dive checks, strict MkDocs, and whitespace checks. AIQ Assist MCP
  consumption remains disabled.
- Generated packages, wheelhouses, detailed operator evidence, credentials, internal repository
  coordinates, signing material, and local paths remain outside git. Artifactory upload, package
  download, signing, attestation, trust-root verification, and external promotion remain
  operator-owned and were not executed.

## v0.1.26 Release Evidence (2026-06-25)

- Release: `v0.1.26`.
- Private-source GitHub release:
  `https://github.com/hubert-cumberdale/aiq-cli/releases/tag/v0.1.26`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release:
  `https://github.com/hubert-cumberdale/attackiq-cli/releases/tag/v0.1.26`.
- Source release commit: `bc85fc96dd663b3f230db5a077313469c3e6987b`.
- Source annotated tag object: `e87fc74beeb702e8b740d3f91b7e55fe459eefdd`.
- Tag-time CI: passed for tag `v0.1.26`, including Python 3.10, 3.11, and 3.12 jobs plus the
  `release-hygiene` job with dependency constraints, release governance, public safety, secret
  scan, strict public mirror dry run, changelog heading, tag/package version alignment, and
  dependency audit (run `28193339998`).
- Strict public mirror export: generated from tag `v0.1.26` into
  `/tmp/attackiq-cli-public-export-20260625T185829Z`; `PUBLICATION_MANIFEST.json` records
  source commit `bc85fc96dd663b3f230db5a077313469c3e6987b`, source snapshot `git-archive`,
  package version `0.1.26`, tree SHA256
  `39e1437695813770b8e222baaeb9a080656316e893682690449f43f3f24afc51`, manifest SHA256
  `39de39b93f62d1bb576c8fc6502b33c1c627d90946a4919b2dea6eaeff165a97`, and no dirty-worktree
  allowance.
- Public mirror snapshot: one-commit snapshot `ad46849452f5d63e5b84caf6df555d8120a095ae`;
  `git rev-list --count HEAD` returned `1`, and
  `python3 scripts/check_public_safety.py --skip-wheel` passed from the snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.26` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.26`; output contains
  `attackiq_cli-0.1.26-py3-none-any.whl`, `constraints.txt`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_SBOM.spdx.json`,
  `ENTERPRISE_DEPENDENCY_INTEGRITY.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`, and generated `SIGNING_ATTESTATION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `70d3623c194c7db1e57fd6ba16bf311dfc36952def76f0ca322045591dfeedaf`.
- Enterprise install constraints SHA256:
  `ac1ac897a51aab7191851a4883161fc65ddd5b2b3e850174529bce9841f9f6ed`.
- Enterprise checksums file SHA256:
  `595eafde4d1d644056e896f970f4fca20caf41cf11db2c1f4eb563239228edd3`.
- Enterprise promotion manifest SHA256:
  `58c607ca054f0d2ea38db2a5e7dda2866401d474f797bc50db2878800c5e6541`.
- Enterprise SBOM SHA256:
  `a8ea37da53ea6831750c7a817e0874bb759f9b1b17c2e95f97627f6a942291a8`.
- Enterprise dependency-integrity SHA256:
  `2922d2f1fdbfa554bef72562fbf1a96626d93a6b05d0ecadb2057eb4ca4ed10b`.
- Enterprise package provenance SHA256:
  `96c7426e7c84bfb71ec16a414fcf90ef7caf46516b349f052d8c38a86faa02d0`.
- Artifactory promotion evidence SHA256:
  `7b8fd33f4da3f46ab87cce549a7e2ae4d432c93ac6b5eb380cf2ee4fda2a12ad`.
- Signing and attestation evidence SHA256:
  `ed114f45a81c0ccc2f63a0abd7fa1536307e1fe22f452cd61af3c2b7dac4cb0c`.
- Enterprise package verification: `python3 scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.26 --require-constraints` passed and confirmed
  manifest/checksum agreement, wheel digest integrity, required install constraints, safe artifact
  filenames, public-safety scan coverage, SBOM, dependency-integrity, and package provenance
  consistency.
- Artifactory promotion evidence: `python3 scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.26 --artifactory-url
  https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.26/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced seven promotion file records.
- Signing and attestation evidence: `python3 scripts/build_signing_attestation_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.26 --signing-profile enterprise-release
  --output /tmp/attackiq-cli-enterprise-package-v0.1.26/SIGNING_ATTESTATION_EVIDENCE.json`
  passed and produced eight signing subjects.
- Enterprise evidence verification: `python3 scripts/verify_enterprise_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.26 --require-artifactory --require-signing` passed and
  cross-checked package identity, local artifact SHA256/size, Artifactory target paths, required
  `--require-constraints` checklists, signing subjects, and expected signing outputs.
- No-Artifactory install simulation: a local wheelhouse and fresh virtual environment under
  `/tmp/attackiq-cli-enterprise-package-v0.1.26` installed `attackiq-cli==0.1.26` offline with
  `--no-index --find-links` and `-c constraints.txt`; `attackiq --version` reported
  `attackiq-cli version 0.1.26`, `attackiq config validate` reported `Config OK`, and
  `python -m pip check` reported no broken requirements.
- Scope boundary: package upload to Artifactory, package download from Artifactory, artifact
  signing, registry attestation, trust-root verification, repository permissions, and
  change-ticket approval remain operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`603 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.26`, both dependency-audit
  commands passed with no known vulnerabilities, release governance passed, public safety passed,
  secret scan passed, doc-link and deep-dive checks passed, strict public mirror check passed, and
  `git diff --check` passed.

## v0.1.25 Release Evidence (2026-05-29)

- Release: `v0.1.25`.
- Private-source GitHub release:
  `https://github.com/hubert-cumberdale/aiq-cli/releases/tag/v0.1.25`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release:
  `https://github.com/hubert-cumberdale/attackiq-cli/releases/tag/v0.1.25`.
- Merge commit: `13f08e008deccc7bcca11cffe05c543871774a3f`.
- Source tag object: `b1b1fe743315df632274eb6b5ae748cd4826a652`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #77
  (run `26661265639`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `13f08e0`
  (run `26662746216`).
- Tag-time CI: passed for tag `v0.1.25`, including the `release-hygiene` job with dependency
  constraints, release governance, public safety, secret scan, strict public mirror dry run,
  changelog heading, tag/package version alignment, and dependency audit (run `26662921772`).
- Strict public mirror export: generated from tag `v0.1.25` into
  `/tmp/attackiq-cli-public-export-20260529T212401Z`; `PUBLICATION_MANIFEST.json` records
  private source commit `13f08e008deccc7bcca11cffe05c543871774a3f`, source snapshot
  `git-archive`, package version `0.1.25`, tree SHA256
  `0e46ee88622d96141c5fe29143878cc231b7509658c83b46a3311dafaeab255d`, manifest SHA256
  `b7d354f3a3bfa12a9157d46eb6245ad7d029091207fe2df70240e83fee62a24d`, and no
  dirty-worktree allowance.
- Public mirror verification: public tag `v0.1.25` has tag object
  `037d0ff927a80773c5d5b63ba6378d732438759d` and peeled commit
  `1b79128702d371b73de38aa7760e1532f7229829`; cloning the tag into
  `/tmp/attackiq-cli-public-verify-v0.1.25-20260529T2206Z` returned `1` from
  `git rev-list --count HEAD`, and `python3 scripts/check_public_safety.py --skip-wheel`
  passed from the clone.
- Public mirror branch boundary: public `main` remained at
  `7cdd6b30366ca5f5b8f13f62357137ed21cea4a8` because updating the one-commit mirror branch
  would require a non-fast-forward operator action. The release was published through the public
  tag and GitHub release.
- Enterprise package promotion artifacts: generated from public tag `v0.1.25` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.25-20260529`; output contains
  `attackiq_cli-0.1.25-py3-none-any.whl`, `constraints.txt`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_SBOM.spdx.json`,
  `ENTERPRISE_DEPENDENCY_INTEGRITY.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`, and generated `SIGNING_ATTESTATION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `95e99671b8f363299035ab5f9e99b12a1de00cc2e3d18c96db799eae8c1b9fd0`.
- Enterprise install constraints SHA256:
  `7fc20008e158ca910c7d0f4a5f9d1d09689a9ef293f180de62ec93b1c9435a3d`.
- Enterprise checksums file SHA256:
  `c0c85a40881fc31d8ceb736fbd59d894687121d7e0e343b7fb647216b27a979a`.
- Enterprise promotion manifest SHA256:
  `c8cea1f0816db777954f7bef8b0b4f7e431b52914fe656c1ca886d20c7a38fb0`.
- Enterprise SBOM SHA256:
  `a036f0c520cc430aac24f4006a90d6d76d2b0e3fe26fcd5723177ba3ca4794f7`.
- Enterprise dependency-integrity SHA256:
  `04021a62aa7560dce0ae272ff91b20b946708431e6d031526a660a50daa711cd`.
- Enterprise package provenance SHA256:
  `451626a40ac06432dd6ed0ca048436393958ed3b16348f79c9a9a969db05e62b`.
- Artifactory promotion evidence SHA256:
  `48bb3f1259064a15a49f268ba58bc8026eb77567f8a0d2ff1f3272335ee5997a`.
- Signing and attestation evidence SHA256:
  `d29f0180270cab05c59310297862218de7c19c66ece445926b9ffed97ab3a32f`.
- Enterprise package verification: `python3 scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.25-20260529 --require-constraints` passed and
  confirmed manifest/checksum agreement, wheel digest integrity, required install constraints,
  safe artifact filenames, public-safety scan coverage, SBOM, dependency-integrity, and package
  provenance consistency.
- Artifactory promotion evidence: `python3 scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.25-20260529 --artifactory-url
  https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.25-20260529/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced seven promotion file records.
- Signing and attestation evidence: `python3 scripts/build_signing_attestation_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.25-20260529 --signing-profile enterprise-release
  --output /tmp/attackiq-cli-enterprise-package-v0.1.25-20260529/SIGNING_ATTESTATION_EVIDENCE.json`
  passed and produced eight signing subjects.
- Enterprise evidence verification: `python3 scripts/verify_enterprise_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.25-20260529 --require-artifactory
  --require-signing` passed and cross-checked package identity, local artifact SHA256/size,
  Artifactory target paths, required `--require-constraints` checklists, signing subjects, and
  expected signing outputs.
- No-Artifactory install simulation: a local wheelhouse and fresh virtual environment under
  `/tmp/attackiq-cli-enterprise-package-v0.1.25-20260529` installed `attackiq-cli==0.1.25`
  offline with `--no-index --find-links` and `-c constraints.txt`; `attackiq --version` reported
  `attackiq-cli version 0.1.25`, `attackiq config validate` reported `Config OK`, and
  `python -m pip check` reported no broken requirements.
- Scope boundary: package upload to Artifactory, package download from Artifactory, artifact
  signing, registry attestation, trust-root verification, repository permissions, and
  change-ticket approval remain operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`523 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.25`, both dependency-audit
  commands passed with no known vulnerabilities, release governance passed, public safety passed,
  secret scan passed, doc-link and deep-dive checks passed, strict public mirror check passed, and
  `git diff --check` passed.

## Enterprise Evidence Verification Workflow (2026-05-27)

- Release: `v0.1.24`.
- Private-source GitHub release:
  `https://github.com/hubert-cumberdale/aiq-cli/releases/tag/v0.1.24`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release:
  `https://github.com/hubert-cumberdale/attackiq-cli/releases/tag/v0.1.24`.
- Merge commit: `e202eb3`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #53
  (run `26487159197`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `e202eb3`
  (run `26487262434`).
- Tag-time CI: passed for tag `v0.1.24`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26487286723`).
- GitHub Actions warning verification: PR, branch, and tag check-run annotation counts were zero,
  including the tag-time `release-hygiene` job. The only log text containing `warning` was Git's
  default-branch hint during checkout initialization, not a GitHub Actions runtime warning.
- Strict public mirror export: generated from tag `v0.1.24` into
  `/tmp/attackiq-cli-public-export-20260527T023446Z`; `PUBLICATION_MANIFEST.json` records
  private source commit `e202eb32fb7e70f868000ad83c4fff44fcf899d8`, source snapshot
  `git-archive`, package version `0.1.24`, tree SHA256
  `6cd2cc683db2ab21a05961e37bf9997413aff7363b596cf389a4a0dc91c95582`, and no
  dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.24` into
  `/tmp/attackiq-cli-public-verify-v0.1.24-20260527T0238Z`; `git rev-list --count HEAD`
  returned `1`, `python3 scripts/check_public_safety.py --skip-wheel` passed, and public
  commit `7cdd6b30366ca5f5b8f13f62357137ed21cea4a8` contains the one-commit source
  snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.24` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.24-20260527`; output contains
  `attackiq_cli-0.1.24-py3-none-any.whl`, `constraints.txt`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`, and generated `SIGNING_ATTESTATION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `cac115adcaa3fca8b89e337bc3a9ea490b8b5f117001e6b319139ec2dd72de6f`.
- Enterprise install constraints SHA256:
  `7fc20008e158ca910c7d0f4a5f9d1d09689a9ef293f180de62ec93b1c9435a3d`.
- Enterprise checksums file SHA256:
  `a12b98da0c3f0870e5b0f4a546d344e8db6e07f2c816cb60137cf2e2e59e0fa1`.
- Enterprise promotion manifest SHA256:
  `02dbb67ad40f044b999772e5711b284a9e43357501780b182c0d65f15676205c`.
- Enterprise package provenance SHA256:
  `936463bb0989ac97c5960c8a5c557e72bf591e71fa2cd932b2e737569a100e32`.
- Artifactory promotion evidence SHA256:
  `79f7707779610d40449313a85c2437a52063df0e64916e40a3614759ef87c1d6`.
- Signing and attestation evidence SHA256:
  `51438da704761dd6d373b18c701889721b95d286fd28ac6cb88c14a3bcc2c3e5`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.24-20260527 --require-constraints` passed before
  evidence generation and confirmed manifest/checksum agreement, wheel digest integrity, required
  install constraints, safe artifact filenames, public-safety scan coverage, and package
  provenance consistency.
- Artifactory promotion evidence: `.venv/bin/python scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.24-20260527 --artifactory-url
  https://artifactory.example.invalid/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.24-20260527/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced five promotion file records for the wheel, `constraints.txt`, `SHA256SUMS`,
  promotion manifest, and package provenance.
- Signing and attestation evidence: `.venv/bin/python scripts/build_signing_attestation_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.24-20260527 --signing-profile enterprise-release
  --output /tmp/attackiq-cli-enterprise-package-v0.1.24-20260527/SIGNING_ATTESTATION_EVIDENCE.json`
  passed and produced six signing subjects for the wheel, `constraints.txt`, `SHA256SUMS`,
  promotion manifest, package provenance, and Artifactory promotion evidence.
- Enterprise evidence verification: `.venv/bin/python scripts/verify_enterprise_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.24-20260527 --require-artifactory
  --require-signing` passed and cross-checked package identity, local artifact SHA256/size,
  Artifactory target paths, required `--require-constraints` checklists, signing subjects, and
  expected signing outputs.
- Scope boundary: package upload to Artifactory, artifact signing, registry attestation,
  trust-root verification, repository permissions, and change-ticket approval remain
  operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`494 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.24`, both dependency-audit
  commands passed with no known vulnerabilities, release governance passed, public safety passed,
  doc-link and deep-dive checks passed, focused enterprise evidence tests passed, focused mypy for
  the new evidence verifier passed, strict public mirror check passed, and `git diff --check`
  passed.

## Required Constraints Evidence Workflow (2026-05-27)

- Release: `v0.1.23`.
- Private-source GitHub release:
  `https://github.com/hubert-cumberdale/aiq-cli/releases/tag/v0.1.23`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release:
  `https://github.com/hubert-cumberdale/attackiq-cli/releases/tag/v0.1.23`.
- Merge commit: `83a6804`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #52
  (run `26484389398`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `83a6804`
  (run `26484519767`).
- Tag-time CI: passed for tag `v0.1.23`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26484780896`).
- GitHub Actions warning verification: PR, branch, and tag check-run annotation lists were empty,
  including the tag-time `release-hygiene` job.
- Strict public mirror export: generated from tag `v0.1.23` into
  `/tmp/attackiq-cli-public-export-20260527T011532Z`; `PUBLICATION_MANIFEST.json` records
  private source commit `83a68047957655c24b0a5385ef1916f44260a4e3`, source snapshot
  `git-archive`, package version `0.1.23`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.23` into
  `/tmp/attackiq-cli-public-verify-v0.1.23-20260527T0121Z`; `git rev-list --count HEAD`
  returned `1`, `python3 scripts/check_public_safety.py --skip-wheel` passed, and public
  commit `d7a16da92fc1832e398a0df5f9dbbfcbdaf36c40` contains the one-commit source
  snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.23` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.23-20260527`; output contains
  `attackiq_cli-0.1.23-py3-none-any.whl`, `constraints.txt`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`, and generated `SIGNING_ATTESTATION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `c87a8267f323c7ec3274b987c963b1fc2686b3e5e2ca5f5f887d6e4a51e9374e`.
- Enterprise install constraints SHA256:
  `7fc20008e158ca910c7d0f4a5f9d1d09689a9ef293f180de62ec93b1c9435a3d`.
- Enterprise package provenance SHA256:
  `e785e94c343bd95e0abbb696b0b18dc76ddbcbdc9a9526ec9884d98a8a785dae`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.23-20260527 --require-constraints` passed before and
  after evidence generation and confirmed manifest/checksum agreement, wheel digest integrity,
  required install constraints, safe artifact filenames, public-safety scan coverage, and package
  provenance consistency.
- Artifactory promotion evidence: `.venv/bin/python scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.23-20260527 --artifactory-url
  https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.23-20260527/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced five promotion file records for the wheel, `constraints.txt`, `SHA256SUMS`,
  promotion manifest, and package provenance. Generated pre-upload and post-download verification
  checklists include `--require-constraints`.
- Signing and attestation evidence: `.venv/bin/python scripts/build_signing_attestation_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.23-20260527 --signing-profile enterprise-release
  --output /tmp/attackiq-cli-enterprise-package-v0.1.23-20260527/SIGNING_ATTESTATION_EVIDENCE.json`
  passed and produced six signing subjects for the wheel, `constraints.txt`, `SHA256SUMS`,
  promotion manifest, package provenance, and Artifactory promotion evidence. Generated
  pre-signing and post-signing checklists include `--require-constraints`.
- Scope boundary: package upload to Artifactory, artifact signing, registry attestation,
  trust-root verification, repository permissions, and change-ticket approval remain
  operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`486 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.23`, both dependency-audit
  commands passed with no known vulnerabilities, release governance passed, public safety passed,
  doc-link and deep-dive checks passed, focused enterprise package/evidence tests passed, focused
  mypy for enterprise evidence helpers passed, strict public mirror check passed, private-reference
  scan for legacy repository names had no matches, and `git diff --check` passed.

## Enterprise Install Constraints Workflow (2026-05-26)

- Release: `v0.1.21`.
- Private-source GitHub release:
  `https://github.com/hubert-cumberdale/aiq-cli/releases/tag/v0.1.21`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release:
  `https://github.com/hubert-cumberdale/attackiq-cli/releases/tag/v0.1.21`.
- Merge commit: `f05361a`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #50
  (run `26456380937`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `f05361a`
  (run `26457252866`).
- Tag-time CI: passed for tag `v0.1.21`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26458384861`).
- GitHub Actions warning verification: PR, branch, and tag check-run annotation lists were empty,
  including the tag-time `release-hygiene` job.
- Strict public mirror export: generated from tag `v0.1.21` into
  `/tmp/attackiq-cli-public-export-20260526T153837Z`; `PUBLICATION_MANIFEST.json` records
  private source commit `f05361ad8cb526dec7b54f86522fb51c66bca00c`, source snapshot
  `git-archive`, package version `0.1.21`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.21` into
  `/tmp/attackiq-cli-public-verify-v0.1.21-20260526T1540Z`; `git rev-list --count HEAD`
  returned `1`, `python3 scripts/check_public_safety.py --skip-wheel` passed, and public
  commit `56159760984a216e59e1ecb6ca02b8e72d879811` contains the one-commit source
  snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.21` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.21-20260526`; output contains
  `attackiq_cli-0.1.21-py3-none-any.whl`, `constraints.txt`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`, and generated `SIGNING_ATTESTATION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `970b31e5bed264636dea6c23a0f2b318e9ea96148244d3bbe0ec55cf530a38e7`.
- Enterprise install constraints SHA256:
  `7fc20008e158ca910c7d0f4a5f9d1d09689a9ef293f180de62ec93b1c9435a3d`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.21-20260526` passed before and after evidence
  generation and confirmed manifest/checksum agreement, wheel digest integrity, install
  constraints digest integrity, safe artifact filenames, public-safety scan coverage, and package
  provenance consistency.
- Artifactory promotion evidence: `.venv/bin/python scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.21-20260526 --artifactory-url
  https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.21-20260526/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced five promotion file records for the wheel, `constraints.txt`, `SHA256SUMS`,
  promotion manifest, and package provenance.
- Signing and attestation evidence: `.venv/bin/python scripts/build_signing_attestation_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.21-20260526 --signing-profile enterprise-release
  --output /tmp/attackiq-cli-enterprise-package-v0.1.21-20260526/SIGNING_ATTESTATION_EVIDENCE.json`
  passed and produced six signing subjects for the wheel, `constraints.txt`, `SHA256SUMS`,
  promotion manifest, package provenance, and Artifactory promotion evidence.
- Scope boundary: package upload to Artifactory, artifact signing, registry attestation,
  trust-root verification, repository permissions, and change-ticket approval remain
  operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`482 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.21`, both dependency-audit
  commands passed, release governance passed, public safety passed, doc-link and deep-dive checks
  passed, focused enterprise package tests passed, focused mypy for enterprise package helpers
  passed, strict public mirror check passed, private-reference scan for legacy repository names had
  no matches, and `git diff --check` passed.

## Signing And Attestation Evidence Workflow (2026-05-26)

- Release: `v0.1.20`.
- Private-source GitHub release: published from tag `v0.1.20`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.20` without package attachments.
- Merge commit: `0fd4ad8`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #49
  (run `26452327577`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `0fd4ad8`
  (run `26452501758`).
- Tag-time CI: passed for tag `v0.1.20`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26452665174`).
- GitHub Actions warning verification: PR, branch, and tag check-run annotation lists were empty,
  including the tag-time `release-hygiene` job.
- Strict public mirror export: generated from tag `v0.1.20` into
  `/tmp/attackiq-cli-public-export-20260526T140554Z`; `PUBLICATION_MANIFEST.json` records
  private source commit `0fd4ad8fa0b59fb88c1d0c033c4c94177f5301bb`, source snapshot
  `git-archive`, package version `0.1.20`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.20` into
  `/tmp/attackiq-cli-public-verify-v0.1.20-20260526T1408Z`; `git rev-list --count HEAD`
  returned `1`, `python3 scripts/check_public_safety.py --skip-wheel` passed, and public
  commit `e1f97944bd2b041bcd5fa15f0f8e9193cf2a7c72` contains the one-commit source
  snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.20` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.20-20260526`; output contains
  `attackiq_cli-0.1.20-py3-none-any.whl`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`, and generated `SIGNING_ATTESTATION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `e9c844ead21b4f9504559362684db4ff9d29fd8c291308c22a3d37ba17719e05`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.20-20260526` passed before and after evidence
  generation and confirmed manifest/checksum agreement, wheel digest integrity, safe artifact
  filenames, public-safety scan coverage, and package provenance consistency.
- Artifactory promotion evidence: `.venv/bin/python scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.20-20260526 --artifactory-url
  https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.20-20260526/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced four promotion file records for the wheel, `SHA256SUMS`, promotion manifest,
  and package provenance.
- Signing and attestation evidence: `.venv/bin/python scripts/build_signing_attestation_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.20-20260526 --signing-profile enterprise-release
  --output /tmp/attackiq-cli-enterprise-package-v0.1.20-20260526/SIGNING_ATTESTATION_EVIDENCE.json`
  passed and produced five signing subjects for the wheel, `SHA256SUMS`, promotion manifest,
  package provenance, and Artifactory promotion evidence.
- Scope boundary: package upload to Artifactory, artifact signing, registry attestation, trust-root
  verification, repository permissions, and change-ticket approval remain operator-owned and
  credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`480 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.20`, both dependency-audit
  commands passed, release governance passed, public safety passed, doc-link and deep-dive checks
  passed, focused signing evidence tests passed, focused mypy for the new helper passed, strict
  public mirror check passed, and `git diff --check` passed.

## Artifactory Promotion Evidence Workflow (2026-05-25)

- Release: `v0.1.19`.
- Private-source GitHub release: published from tag `v0.1.19`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.19` without package attachments.
- Merge commit: `f49ec1e`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #48
  (run `26422163576`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `f49ec1e`
  (run `26422267688`).
- Tag-time CI: passed for tag `v0.1.19`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26422335712`).
- GitHub Actions warning verification: PR, branch, and tag check-run annotation lists were empty,
  including the tag-time `release-hygiene` job.
- Strict public mirror export: generated from tag `v0.1.19` into
  `/tmp/attackiq-cli-public-export-20260525T223513Z`; `PUBLICATION_MANIFEST.json` records source
  commit `f49ec1ed347508a50c8dd04fe54eefda5ca03700`, source snapshot `git-archive`, package
  version `0.1.19`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.19` into
  `/tmp/attackiq-cli-public-verify-v0.1.19-20260525T2238`; `git rev-list --count HEAD` returned
  `1`, `python3 scripts/check_public_safety.py --skip-wheel` passed, and public commit
  `716354728ec89fbe9e567a256576f2e593fa9540` contains the one-commit source snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.19` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.19-20260525`; output contains
  `attackiq_cli-0.1.19-py3-none-any.whl`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, `ENTERPRISE_PACKAGE_PROVENANCE.json`, and generated
  `ARTIFACTORY_PROMOTION_EVIDENCE.json`.
- Enterprise wheel SHA256:
  `92d0a951738220cfa3cde1633a7eb2d934bb560e7d0a5cc38f0f453e809ded7c`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.19-20260525` passed and confirmed manifest/checksum
  agreement, wheel digest integrity, safe artifact filenames, public-safety scan coverage, and
  package provenance consistency.
- Artifactory promotion evidence: `.venv/bin/python scripts/build_artifactory_promotion_evidence.py
  /tmp/attackiq-cli-enterprise-package-v0.1.19-20260525 --artifactory-url
  https://artifactory.example.com/artifactory --repository-path api/pypi/attackiq-cli-local
  --output /tmp/attackiq-cli-enterprise-package-v0.1.19-20260525/ARTIFACTORY_PROMOTION_EVIDENCE.json`
  passed and produced four promotion file records for the wheel, `SHA256SUMS`, promotion manifest,
  and package provenance.
- Scope boundary: package upload to Artifactory, artifact signing, registry attestation, repository
  permissions, and change-ticket approval remain operator-owned and credential-free from this
  repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`473 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.19`, both dependency-audit
  commands passed, release governance passed, public safety passed, doc-link and deep-dive checks
  passed, focused Artifactory evidence tests passed, focused mypy for the new helper passed, and
  `git diff --check` passed.

## GitHub Actions Runtime Workflow (2026-05-25)

- Release: `v0.1.18`.
- Private-source GitHub release: published from tag `v0.1.18`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.18` without package attachments.
- Merge commit: `b10b7b1`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #47
  (run `26418485642`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `b10b7b1`
  (run `26418956646`).
- Tag-time CI: passed for tag `v0.1.18`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26419970594`).
- GitHub Actions warning verification: PR, branch, and tag check-run annotation lists were empty,
  including the tag-time `release-hygiene` job; no Node 20 deprecation annotation remained after
  moving to `actions/checkout@v6` and `actions/setup-python@v6`.
- Strict public mirror export: generated from tag `v0.1.18` into
  `/tmp/attackiq-cli-public-export-20260525T212335Z`; `PUBLICATION_MANIFEST.json` records source
  commit `b10b7b13332b154194727248e81fcf31a9382a19`, source snapshot `git-archive`, package
  version `0.1.18`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.18` into
  `/tmp/attackiq-cli-public-verify-v0.1.18-20260525T2128`; `git rev-list --count HEAD` returned
  `1`, `python3 scripts/check_public_safety.py --skip-wheel` passed, and public commit
  `dbfcd734cf019c289e7ef88d1b3d33aa434e0276` contains the one-commit source snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.18` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.18-20260525`; output contains
  `attackiq_cli-0.1.18-py3-none-any.whl`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, and `ENTERPRISE_PACKAGE_PROVENANCE.json`.
- Enterprise wheel SHA256:
  `88b48095cf786d700d31f4bb43006dbde844397e40415591e3409a4fdd4cb498`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.18-20260525` passed and confirmed manifest/checksum
  agreement, wheel digest integrity, safe artifact filenames, public-safety scan coverage, and
  package provenance consistency.
- Scope boundary: package upload to Artifactory, artifact signing, and registry attestation remain
  operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`467 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.18`, both dependency-audit
  commands passed, release governance passed, public safety passed, doc-link and deep-dive checks
  passed, and `git diff --check` passed.

## Enterprise Package Provenance Workflow (2026-05-25)

- Release: `v0.1.17`.
- Private-source GitHub release: published from tag `v0.1.17`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.17` without package attachments.
- Merge commit: `7cbef9e`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #46
  (run `26416441445`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `7cbef9e`
  (run `26416648243`).
- Tag-time CI: passed for tag `v0.1.17`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26416730506`).
- Strict public mirror export: generated from tag `v0.1.17` into
  `/tmp/attackiq-cli-public-export-20260525T193652Z`; `PUBLICATION_MANIFEST.json` records source
  commit `7cbef9e882943ba9a6ba37476ab7a78f4ae1e380`, source snapshot `git-archive`, package
  version `0.1.17`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.17` into
  `/tmp/attackiq-cli-public-verify-v0.1.17-20260525`; `git rev-list --count HEAD` returned `1`,
  `python3 scripts/check_public_safety.py --skip-wheel` passed, and public commit
  `07a11c1b0c27e54cc411d337642b1c4b695c86ba` contains the one-commit source snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.17` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.17-20260525`; output contains
  `attackiq_cli-0.1.17-py3-none-any.whl`, `SHA256SUMS`,
  `ENTERPRISE_PROMOTION_MANIFEST.json`, and `ENTERPRISE_PACKAGE_PROVENANCE.json`.
- Enterprise wheel SHA256:
  `f0b3bd5f763f8bfc037095dfa67183c60bd175e1d884f44eb1137db861d1380f`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.17-20260525` passed and confirmed manifest/checksum
  agreement, wheel digest integrity, safe artifact filenames, public-safety scan coverage, and
  package provenance consistency.
- Scope boundary: package upload to Artifactory, artifact signing, and registry attestation remain
  operator-owned and credential-free from this repository.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`467 passed`),
  `.venv/bin/python -m attackiq_cli --version` reported `attackiq-cli version 0.1.17`, both
  dependency-audit commands passed, release governance passed, public safety passed, doc-link and
  deep-dive checks passed, `git diff --check` passed, and the enterprise package provenance path
  smoke-tested successfully against public tag `v0.1.16` before final `v0.1.17` package
  generation.

## Enterprise Package Verification Workflow (2026-05-25)

- Release: `v0.1.16`.
- Private-source GitHub release: published from tag `v0.1.16`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.16` without package attachments.
- Merge commit: `e546a4c`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #45
  (run `26414824760`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `e546a4c`
  (run `26414926126`).
- Tag-time CI: passed for tag `v0.1.16`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26415006955`).
- Strict public mirror export: generated from tag `v0.1.16` into
  `/tmp/attackiq-cli-public-export-20260525T184932Z`; `PUBLICATION_MANIFEST.json` records source
  commit `e546a4c07b8368ca7f5ceb0fe0f2be74e2024034`, source snapshot `git-archive`, package
  version `0.1.16`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.16` into
  `/tmp/attackiq-cli-public-verify-v0.1.16-20260525`; `git rev-list --count HEAD` returned `1`,
  `python3 scripts/check_public_safety.py --skip-wheel` passed, and public commit
  `30b069c8975d5ba9e449c0f30737348559de0a68` contains the one-commit source snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.16` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.16-20260525`; output contains
  `attackiq_cli-0.1.16-py3-none-any.whl`, `SHA256SUMS`, and
  `ENTERPRISE_PROMOTION_MANIFEST.json`.
- Enterprise wheel SHA256:
  `48aaac591d2ec83d162e263cf59a4333557d61b539ca9e6675b21933f140163f`.
- Enterprise package verification: `.venv/bin/python scripts/verify_enterprise_package.py
  /tmp/attackiq-cli-enterprise-package-v0.1.16-20260525` passed and confirmed manifest/checksum
  agreement, wheel digest integrity, safe artifact filenames, and public-safety scan coverage.
- Scope boundary: package upload to Artifactory remained operator-owned and credential-free from
  this repository. SBOM/provenance generation was deferred for `v0.1.16`; current workflows now
  generate SBOM, dependency-integrity, and package provenance evidence.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`465 passed`),
  `.venv/bin/python -m attackiq_cli --version` reported `attackiq-cli version 0.1.16`, both
  dependency-audit commands passed, release governance passed, public safety passed, doc-link and
  deep-dive checks passed, `git diff --check` passed, and the enterprise package verifier
  smoke-tested successfully against the previous `v0.1.15` package before final `v0.1.16`
  package generation.

## Enterprise Package Promotion Workflow (2026-05-24)

- Release: `v0.1.15`.
- Private-source GitHub release: published from tag `v0.1.15`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.15`.
- Merge commit: `b6a01c1`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #44
  (run `26374941264`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `b6a01c1`
  (run `26375022189`).
- Tag-time CI: passed for tag `v0.1.15`, including release-hygiene checks for dependency
  constraints, release governance, public safety, strict public mirror dry run, changelog heading,
  tag/package version alignment, and dependency audit (run `26375114133`).
- Strict public mirror export: generated from tag `v0.1.15` into
  `/tmp/attackiq-cli-public-export-20260524T232951Z`; `PUBLICATION_MANIFEST.json` records source
  commit `b6a01c18f17f45aaadeef4a63666dcd0efd39667`, source snapshot `git-archive`, package
  version `0.1.15`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.15` into
  `/tmp/attackiq-cli-public-verify-v0.1.15-20260524`; `git rev-list --count HEAD` returned `1`,
  `python3 scripts/check_public_safety.py --skip-wheel` passed, and public commit
  `985d253d36a1b6e2a0477505642983efc66ca7db` contains the one-commit source snapshot.
- Enterprise package promotion artifacts: generated from public tag `v0.1.15` into
  `/tmp/attackiq-cli-enterprise-package-v0.1.15-20260524`; output contains
  `attackiq_cli-0.1.15-py3-none-any.whl`, `SHA256SUMS`, and
  `ENTERPRISE_PROMOTION_MANIFEST.json`.
- Enterprise wheel SHA256:
  `39d619a11792857bd1e121e2529f4debec3345a10046a0d746df56adf29f5cc5`.
- Scope boundary: package upload to Artifactory remained operator-owned and credential-free from
  this repository. SBOM/provenance generation was deferred for `v0.1.15`; current workflows now
  generate SBOM, dependency-integrity, and package provenance evidence.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`459 passed`),
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.15`, both dependency-audit
  commands passed, release governance passed, public safety passed, doc-link and deep-dive checks
  passed, `git diff --check` passed, and the enterprise package builder smoke-tested successfully
  against public tag `v0.1.14` before final `v0.1.15` package generation.

## Public Mirror Workflow (2026-05-22)

- Release: `v0.1.14`.
- Private-source GitHub release: published from tag `v0.1.14`.
- Public source mirror: `https://github.com/hubert-cumberdale/attackiq-cli`.
- Public GitHub release: published from public tag `v0.1.14`.
- Merge commit: `38af81a`.
- PR CI: passed on Python 3.10, 3.11, and 3.12 for PR #43
  (run `26300374202`).
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `38af81a`
  (run `26300543652`).
- Tag-time CI: passed on Python 3.10, 3.11, and 3.12 for tag `v0.1.14`, including
  release-hygiene checks for dependency constraints, release governance, public safety, strict
  public mirror dry run, changelog heading, tag/package version alignment, and dependency audit
  (run `26300567465`).
- Strict public mirror export: generated from tag `v0.1.14` into
  `/tmp/attackiq-cli-public-export-v0.1.14-20260522`; `PUBLICATION_MANIFEST.json` records source
  commit `38af81a96e1b3716bab66f1a7984960e85f9ad93`, source snapshot `git-archive`, package
  version `0.1.14`, and no dirty-worktree allowance.
- Public mirror verification: cloned public tag `v0.1.14` into
  `/tmp/attackiq-cli-public-verify-v0.1.14-20260522`; `git rev-list --count HEAD` returned `1`,
  `python3 scripts/check_public_safety.py --skip-wheel` passed, and a blocked-reference scan found
  no private repository names, workstation paths, or lab-only references.
- Purpose: add the no-history public mirror workflow for `hubert-cumberdale/attackiq-cli`.
- Added guardrail: `scripts/check_public_mirror.py` exports a sanitized source snapshot, writes
  `PUBLICATION_MANIFEST.json`, runs public-safety validation, initializes a one-commit public-style
  repository, and rejects repo-local export directories.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`451 passed`),
  `.venv/bin/python scripts/check_public_mirror.py --allow-dirty` passed with wheel inspection,
  `.venv/bin/attackiq --version` reported `attackiq-cli version 0.1.14`, both dependency-audit
  commands passed, release governance passed, doc-link and deep-dive checks passed, and
  `git diff --check` passed.
- Scope boundary: first public enterprise delivery was GitHub source only. Package registry
  promotion, Artifactory publishing, and package artifacts were deferred for `v0.1.14`; current
  workflows now build credential-free enterprise package artifacts from public tags.

## Public Release (2026-05-22)

- Release: `v0.1.13`.
- GitHub release: published from tag `v0.1.13`.
- Merge commit: `529f41d`.
- Branch CI: passed on Python 3.10, 3.11, and 3.12 for commit `529f41d`
  (run `26297870834`).
- Tag-time CI: passed on Python 3.10, 3.11, and 3.12 for tag `v0.1.13`, including
  release-hygiene checks for dependency constraints, release governance, public safety, changelog
  heading, tag/package version alignment, and dependency audit (run `26297913026`).
- Clean install smoke: cloned tag `v0.1.13` into
  `/tmp/aiq-cli-release-checkout-v0.1.13-20260522`, installed into
  `/tmp/aiq-cli-install-smoke-v0.1.13-20260522` with the tagged `constraints.txt`; `attackiq
  --version` reported `attackiq-cli version 0.1.13`, `pip check` passed, and
  `attackiq backup configs --help` rendered.
- Purpose: prepare the repository for public GitHub publication and downstream enterprise package
  promotion.
- Added guardrail: `scripts/check_public_safety.py` scans tracked files and built wheels for
  blocked private references and disallowed artifact paths.
- Removed tracked historical handoffs, review notes, taskpacks, lab scenario payloads, and
  sibling-repository planning docs.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed (`445 passed`),
  `python3 scripts/check_public_safety.py`, both dependency-audit commands, `attackiq --version`,
  release governance, `git diff --check`, and clean wheel inspection passed.
- Scope boundary: Artifactory or other enterprise package promotion is downstream of the validated
  wheel; this repo does not store enterprise registry credentials or publish automation. The
  current tree is scrubbed, but existing git history still contains removed private/lab files; do
  not make this repository public in place until history handling is explicitly approved.

## Production Promotion (2026-05-22)

- Release: `v0.1.12`
- GitHub release: published from tag `v0.1.12`.
- Purpose: release the first redacted configuration-backup workflow:
  `attackiq backup configs`.
- Local verification: `.venv/bin/python scripts/quality_gate.py` passed, doc links, release
  governance, deep-dive render/verification, both dependency-audit commands, `attackiq --version`,
  editable package metadata refresh, and `git diff --check` passed.
- Scope boundary: standard documented CLI work remains approved; configuration-backup artifacts
  must remain redacted and outside git; destructive, high-volume, custom-scenario, restore/apply,
  customer-mode, or raw connector-configuration workflows still require separate approval.

## Previous Production Promotions

- `v0.1.11` added the opt-in live smoke harness for the approved low-risk production roster and
  kept lab-only health gates outside the production roster.
- `v0.1.10` aligned the production operator runbook with release hygiene, clean install smoke, and
  dependency-audit expectations.

## Dependency Constraints

- `constraints.txt` pins the validated CI/release tooling environment.
- CI installs branch/PR and tag-release jobs with `python -m pip install -c constraints.txt ...`.
- `scripts/check_dependency_constraints.py` verifies runtime, dev, and release-audit direct
  dependencies are covered by exact pins in `constraints.txt`.
- `scripts/check_release_governance.py` verifies:
  - `docs/STATE.md` declares the current production-ready release.
  - During pre-tag release prep, `docs/STATE.md` may also declare a prepared release candidate.
  - Either the current production-ready release or prepared release candidate matches
    `pyproject.toml` and `CHANGELOG.md`.
  - `docs/VERSIONING.md` documents that current-release selection must not use highest-version tag
    sorting and records the historical `v1.0.0` exception.
- Stale historical tag governance remains tracked in GitHub issue #34 for the `v1.0.0` exception.
