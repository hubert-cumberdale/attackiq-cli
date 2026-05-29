# Sub-Agent Scope and Response Format

## Scope Boundaries
- Work only within the task slice assigned by the lead.
- Avoid cross-cutting edits (no repo-wide refactors, no config/global policy changes).
- Do not touch secrets or credentials; never log tokens or customer data.
- Keep changes minimal and reversible; prefer edits within a single module or doc.
- If a request conflicts with scope or security rules, stop and ask the lead.

## Standard Response Format
- Findings: risks, gaps, or issues discovered ("None" if not applicable).
- Changes: list files touched and what was changed.
- Tests: what was run and results (or "Not run" with reason).
- Open Questions: blockers or decisions needed by the lead ("None" if not applicable).

## Response Format Checklist
- Include all four sections in order.
- Keep bullets concise and actionable.
- List exact files touched using relative paths.
