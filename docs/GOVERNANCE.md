# Governance

## Scope Control

- Own the task scope, acceptance criteria, and security requirements before editing.
- Keep cross-cutting changes small and reviewable.
- Prefer read-only workflows and dry-run defaults for operator-facing commands.
- Treat production writes, destructive actions, high-volume activity, and tenant-data handling as
  separately approved work.

## Safety Rules

- Do not commit tokens, cookies, bearer headers, HAR files, raw API responses, tenant payloads, or
  generated runtime artifacts.
- Keep TLS verification enabled unless an explicitly documented test case requires `--insecure`.
- Redact secrets and private identifiers in logs, errors, docs, and test fixtures.
- Keep generated package output, MkDocs `site/`, live-smoke evidence, and backup artifacts outside
  git.
- Run `python3 scripts/check_public_safety.py` and the strict public mirror check before
  publishing source or package artifacts.

## Change Discipline

- Match existing CLI, service, test, and documentation patterns.
- Add focused tests for changed behavior.
- Update `README.md`, `docs/STATE.md`, and feature docs when user-visible command behavior changes.
- Use `docs/SESSION_BOOTSTRAP.md` when a task requires docs/code parity checks.

## Release Governance

- `pyproject.toml`, `src/attackiq_cli/__init__.py`, `CHANGELOG.md`, and `docs/STATE.md` must agree
  on the current release.
- Do not infer the current production release by sorting tags; see `docs/VERSIONING.md`.
- Before release, run dependency constraints, release governance, public-safety, public-mirror,
  quality, doc-link, deep-dive, dependency-audit, and whitespace checks.

## Related Resources

- Session bootstrap workflow: `docs/SESSION_BOOTSTRAP.md`
- Production readiness: `docs/PRODUCTION_READINESS.md`
- Public release guidance: `docs/PUBLIC_RELEASE.md`
- Sub-agent scope and response format: `docs/sub-agent-scope.md`
- Contributor guidance: `CONTRIBUTING.md`
