# Screenshots

Screenshots make local playbooks easier to use, but they can expose private data. Treat every
screenshot as sensitive until reviewed.

## Storage

Store docs screenshots under:

```text
docs/assets/
```

Use descriptive filenames:

```text
docs/assets/scenario-upload-dry-run.png
docs/assets/cloud-bas-coverage.png
```

## Rules

- Use synthetic or redacted data.
- Mask tenant names, hostnames, private IPs, usernames, tokens, cookies, and email addresses.
- Do not include browser developer tools if request headers or cookies are visible.
- Prefer fixture-generated screenshots where possible.
- Record the command, fixture, or route used to create the screenshot.

## Review Checklist

Before committing a screenshot:

1. Zoom in and inspect all text.
2. Confirm no secrets or private identifiers are visible.
3. Confirm the image supports a documented workflow.
4. Add or update the page that references it.
