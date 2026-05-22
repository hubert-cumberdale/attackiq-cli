# Regression Testing Strategy

Regression testing should make new capabilities safe to extend without requiring live AttackIQ or
sibling repo access by default.

## Test Layers

| Layer | Scope | Network |
| --- | --- | --- |
| Unit | Pure helpers, parsing, validation, output normalization. | No |
| CLI contract | Typer commands with mocked services and temp files. | No |
| Adapter fixture | Catalog/EASM imports against local fixtures. | No |
| HTTP client | Mocked `httpx` behavior, auth, redaction, retries. | No |
| Integration | Local repo or local service workflows. | Opt-in |
| Live | Configured AttackIQ tenant or external providers. | Explicit opt-in only |

## Proposed Pytest Markers

Future marker set:

- `unit`
- `cli`
- `adapter`
- `integration`
- `live`
- `slow`

Live tests must require explicit environment variables and should skip by default.

## Quality Gate

The standard local gate is:

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src tests --cache-dir /tmp/aiq-cli-mypy
.venv/bin/python -m pytest -q
python3 scripts/check_doc_links.py
mkdocs build
```

Docs-only changes should run `python3 scripts/check_doc_links.py` and `mkdocs build` at minimum.

## Catalog Regression Fixtures

Catalog adapter tests should include:

- minimal valid record
- unsupported contract version
- missing required field
- invalid enum value
- duplicate ID
- future domain record
- planned or gap record without executable scenario ID

## EASM Regression Fixtures

External exposure export adapter tests should include:

- empty export
- one valid exposure recommendation
- unknown confidence value
- out-of-scope target marker
- evidence link without raw sensitive payload
- duplicate asset or issue input

## Golden Outputs

Use golden outputs for:

- coverage matrices
- assessment plans
- exported JSON/CSV summaries
- generated docs fragments

Golden files should be compact, deterministic, and reviewed when behavior changes.
