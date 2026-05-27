# Security Policy

## Supported Releases

The current supported release line is documented in `docs/STATE.md`. Patch releases may include
security hardening, dependency updates, redaction fixes, and public-safety guard improvements.

## Reporting a Vulnerability

Do not open public issues that include tokens, tenant data, private hostnames, raw API responses,
browser cookies, HAR files, or screenshots containing tenant data.

Report vulnerabilities through the repository maintainer's private security contact path. Include:

- affected version and commit
- command or workflow involved
- sanitized reproduction steps
- expected impact
- confirmation that no secrets or tenant payloads are included

## Secret Handling

The CLI must not log or persist bearer tokens, account tokens, JWTs, cookies, auth headers, signed
URLs, connector secrets, private key material, or raw browser-captured session data.

Use environment variables such as `ATTACKIQ_ACCOUNT_TOKEN` and `ATTACKIQ_JWT` for automation.
Configuration-backup artifacts are redacted planning artifacts; secret values must be restored from
the authoritative secret manager.

## Release Guardrails

Before publication or enterprise package promotion, run:

```bash
python3 scripts/check_public_safety.py
python3 scripts/quality_gate.py
```

Release candidates must keep generated packages, raw tenant output, local runtime caches, and
browser-captured artifacts outside git.
