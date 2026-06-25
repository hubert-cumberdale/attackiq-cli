# Release-Prep Evidence Checklist

Use this checklist before creating any release tag. It captures the release-prep evidence that must
exist before tag creation is approved. It does not create a tag, publish a public mirror, upload a
package, or replace the post-tag strict public mirror validation.

Keep filled evidence records outside git when they include operator names, workstation paths,
private package indexes, internal tickets, audit-log URLs, or generated package directories.

## Release Candidate Identity

| Field | Value |
| --- | --- |
| Candidate version | `X.Y.Z` |
| Candidate commit | `<commit-sha>` |
| Evidence date UTC | `<YYYY-MM-DDTHH:MM:SSZ>` |
| Evidence owner | `<enterprise release record>` |
| Tag approval status | `<approved | blocked | not requested>` |

## Pre-Tag Required Checks

Run these checks from the release candidate branch before creating a tag:

```bash
python3 scripts/check_dependency_constraints.py
python3 scripts/check_public_safety.py
python3 scripts/check_secret_scan.py
python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel
.venv/bin/pip-audit
.venv/bin/pip-audit -r constraints.txt --no-deps
.venv/bin/python scripts/quality_gate.py --no-mkdocs
```

Record each result:

| Check | Command | Required evidence |
| --- | --- | --- |
| Dependency constraints | `python3 scripts/check_dependency_constraints.py` | Dependency metadata and `constraints.txt` are aligned. |
| Public safety | `python3 scripts/check_public_safety.py` | Tracked source files and wheel contents are public-safe. |
| Secret scan | `python3 scripts/check_secret_scan.py` | Findings are absent or match reviewed allowlist entries. |
| Public mirror dry run | `python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel` | Export manifest is generated, public repository target is correct, and the source snapshot is public-safe. |
| Installed dependency audit | `.venv/bin/pip-audit` | No unresolved known vulnerabilities in the installed release-prep environment. |
| Constraints audit | `.venv/bin/pip-audit -r constraints.txt --no-deps` | No unresolved known vulnerabilities in the pinned constraints record. |
| Local quality gate | `.venv/bin/python scripts/quality_gate.py --no-mkdocs` | Governance, safety, mirror dry run, MCP, Ruff, mypy, pytest, and doc-link checks pass. |

Any failed command blocks tag creation until the failure is remediated or an explicit exception is
approved in the enterprise release record.

## Post-Tag Strict Mirror Check

After tag approval and tag creation, run the strict public mirror validation before pushing the
public mirror or creating a public GitHub release:

```bash
python3 scripts/check_public_mirror.py --ref vX.Y.Z
```

The strict command must validate a clean tagged source tree, built wheel, publication manifest, and
single-commit public-style snapshot. Record the generated `PUBLICATION_MANIFEST.json` location in
the external release record, not in repo-owned release notes.

## Evidence Boundaries

Allowed in repo-owned summaries:

- candidate version and public commit SHA
- command names and pass/fail status
- public-safe failure summaries
- public export manifest filename without private local paths

Keep outside git:

- generated public export directories
- wheelhouses, local virtual environments, and package directories
- private package indexes, credentials, `.netrc`, pip config files, and signed URLs
- operator names, change-ticket identifiers, audit-log URLs, and private workstation paths
