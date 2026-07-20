# Review Standards

Reviews should focus on behavior, safety, regressions, and maintainability.

## General Review Checklist

- Scope matches the request.
- Unrelated refactors are absent or justified.
- User-facing behavior is documented.
- Tests cover success and failure cases.
- Errors fail closed and explain remediation.
- Secrets, headers, cookies, tokens, and private artifacts are redacted.
- New network calls use TLS verification and explicit timeouts.

## API and Adapter Changes

- Contract version is documented.
- Malformed input is rejected early.
- Missing sibling repos or files produce clear errors.
- Auth is optional only when the source truly does not require it.
- Live writes are apply-gated.
- Dry-run output documents its redaction boundary and does not imply that values rendered verbatim
  are sanitized.

## CLI UX Changes

- Help text is accurate and concise.
- Defaults are safe.
- Output is structured when automation is likely.
- File writes create parent directories only when appropriate.
- JSON/CSV outputs remain stable or the change is called out.

## Documentation Changes

- Links resolve locally.
- README stays short and points to deeper docs.
- Playbooks use real commands or clearly mark future commands.
- Screenshots are redacted or synthetic.
- Private repo assumptions are documented as local-only.

## Custom Scenario Changes

- Scenario behavior is benign or explicitly guarded.
- Cleanup is documented.
- Endpoint protection or other EDR controls are never disabled, killed, unloaded, or reconfigured.
- Scenario Wizard packages are generated artifacts and should not be committed unless explicitly
  approved.

## Review Outputs

When performing a review, report:

1. Findings ordered by severity.
2. Open questions or assumptions.
3. Test gaps or residual risk.
4. Brief summary only after findings.
