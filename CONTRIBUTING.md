# Contributing

Thanks for improving the AttackIQ CLI. Keep changes small, tested, and aligned with repository standards.

## Agent Governance
See the governance hub at `docs/GOVERNANCE.md` for scope rules, approvals, and response format.

## Development Setup
```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
pip install -e ".[dev,docs]"
pytest
```

## Style and Testing
- Python 3.10+ only; 4-space indentation; line length 100.
- Run `ruff check src tests` for linting.
- Add focused pytest tests for new behavior or bug fixes.
- Run `mkdocs build` when changing local wiki, playbook, or architecture docs.

## Security Expectations
- Never log or commit secrets; prefer environment variables.
- New network calls must have explicit timeouts and TLS verification.
- Redact tokens and credentials in logs and error messages.

## Agent Contributions
- Follow governance rules in `docs/GOVERNANCE.md` and `docs/sub-agent-scope.md`.
- Use skills from `skills/README.md` when tasks match their scope.
- Reuse shared snippets from `docs/agent-snippets.md`.
- Provide responses in the standard agent format when acting as a sub-agent.

## Agent Onboarding
Start with the governance hub at `docs/GOVERNANCE.md` to understand scope boundaries,
approval rules, and response format expectations. Use the skills index to select the right
playbook before making changes.

## Agent Checklist
- Confirm the task scope and success criteria with the lead.
- Avoid cross-cutting edits; keep changes local and reversible.
- Redact secrets and avoid logging sensitive fields.
- Report tests run (or why they were skipped).

## Pull Requests
- Keep PRs scoped to one logical change.
- Include a brief summary and testing notes.
- Add screenshots or command examples when output changes.
