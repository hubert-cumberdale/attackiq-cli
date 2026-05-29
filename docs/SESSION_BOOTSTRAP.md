# Session Bootstrap Deep Dive

Use this runbook when a task requires code/docs parity checks or multi-file documentation updates.

## Goals

- Rebuild context from authoritative sources: code, CLI help, tests, and current docs.
- Detect and correct documentation drift with minimal duplication.
- Keep public docs free of tenant data, private repository names, workstation paths, and raw
  browser-captured artifacts.

## Prerequisites

- Work from the repository root.
- Use local CLI help as the source of truth for command and flag surfaces.
- Prefer linking docs together over restating the same behavior in multiple places.

## Loop 1: Bootstrap Context

Read the high-level docs for current contracts:

- `README.md`
- `docs/GOVERNANCE.md`
- `docs/STATE.md`
- `docs/ARCHITECTURE.md`
- feature deep dives relevant to the task, such as `docs/CALL_FLOW.md`, `docs/TUI_FLOW.md`,
  `docs/EXPORT_FLOW.md`, and `docs/JOINER_FLOW.md`
- `docs/JOINER.md` when joiner or det-pipeline work is in scope

## Loop 2: Verify Behavior Against Code

Confirm command tree and flags from CLI help:

```bash
.venv/bin/attackiq --help
.venv/bin/attackiq call --help
.venv/bin/attackiq join --help
.venv/bin/attackiq tui --help
.venv/bin/attackiq export assessments --help
.venv/bin/attackiq backup configs --help
```

Confirm implementation details from code:

- `src/attackiq_cli/cli.py`
- `src/attackiq_cli/services.py`
- `src/attackiq_cli/client.py`
- `src/attackiq_cli/backup.py`
- `src/attackiq_cli/joiner/cli.py`
- `src/attackiq_cli/joiner/det_pipeline.py`

Capture only observable behavior and explicit invariants: required args, defaults, validation
rules, warnings/errors, mode-specific semantics, and redaction behavior.

## Loop 3: Patch Docs With Minimal Duplication

1. Update user-facing command docs in `README.md`.
2. Update canonical state/reference docs in `docs/STATE.md`.
3. Update workflow-specific docs for changed behavior.
4. Add cross-links when introducing new document entrypoints.

## Loop 4: Validate

Run the relevant checks:

```bash
python3 scripts/check_public_safety.py --skip-wheel
python3 scripts/check_public_mirror.py --allow-dirty --skip-wheel
python3 scripts/check_doc_links.py
python3 scripts/render_deep_dives.py --check
python3 scripts/verify_deep_dives.py
```

Use the full quality gate before release or when code behavior changed:

```bash
python3 scripts/quality_gate.py
```

## Drift Checklist

- Does every documented command or flag exist in `attackiq --help` output?
- Do mode-dependent flags document their scope?
- Are defaults and required arguments accurate?
- Are TLS, auth, redaction, and output-retention rules still correct?
- Do docs avoid conflicting statements across `README.md`, `docs/STATE.md`, and feature docs?
