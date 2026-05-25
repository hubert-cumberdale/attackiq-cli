# Repository Guidelines

## Project Structure & Module Organization
- `src/attackiq_cli/`: core CLI package (entry points in `src/attackiq_cli/cli.py` and `src/attackiq_cli/__main__.py`).
- `src/attackiq_cli/openapi.yaml`: bundled OpenAPI schema used at runtime.
- `tests/`: pytest suite; tests are named `test_*.py`.
- `scripts/`: one-off utilities (e.g., `scripts/export_scenarios_ttp.py`).

## Build, Test, and Development Commands
- `python -m venv .venv` and activate it: set up a local virtual environment.
- `pip install -e ".[dev]"`: install the CLI in editable mode with dev tools.
- `pytest`: run the test suite.
- `attackiq --help`: verify the CLI entry point is working.

## Coding Style & Naming Conventions
- Python 3.10+ is required; keep code compatible with that baseline.
- Indentation: 4 spaces, line length 100 (Ruff default for this repo).
- Modules and functions: `snake_case`; classes: `PascalCase`.
- Use Ruff for linting: `ruff check src tests`.

## Testing Guidelines
- Framework: pytest.
- Test files live in `tests/` and are named `test_*.py`.
- Prefer small, focused unit tests for CLI helpers and spec parsing.
- Add tests for new behavior and bug fixes alongside code changes.

## Secure-by-Default Engineering
- Secrets: never log, echo, or commit tokens; prefer env vars and redact in errors.
- Any new network call should validate TLS, set explicit timeouts, and fail closed.
- Minimize and pin dependencies; avoid installing unused packages; prefer maintained libs.
- Validate and sanitize untrusted input; prefer allowlists over denylists.
- Avoid shelling out or dynamic code loading unless required; document risk if used.
- Logging: redact secrets/PII; avoid verbose logs in default paths.

### Language Baselines (major languages)
- Python: use `httpx` timeouts/retries; prefer `subprocess.run([...], check=True)`; use
  `yaml.safe_load`; avoid `eval`/`exec`.
- JavaScript/TypeScript: pin deps; avoid `child_process` with untrusted input; use
  `node:fs/promises` and `path` for safe paths; set request timeouts (fetch/undici).
- Go: use `context` with deadlines; configure `http.Client{Timeout: ...}`; avoid `os/exec`
  with untrusted input; use `filepath.Clean`.
- Rust: avoid `unsafe` unless justified; use `reqwest`/`hyper` with timeouts; prefer
  `serde` with typed structs over raw maps; avoid `Command` with untrusted input.
- Java: set `HttpClient` timeouts; use `SecureRandom`; disable XXE in XML parsers; avoid
  reflection/dynamic class loading for untrusted input.
- C/C++: avoid unsafe string APIs; use bounds-checked functions; enable compiler warnings
  and sanitizers when available.

### Secure-by-Default Examples (reference patterns)
- Python (httpx):
  ```python
  with httpx.Client(timeout=10.0) as client:
      resp = client.get(url)
      resp.raise_for_status()
  ```
- JavaScript (fetch with timeout):
  ```js
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  const resp = await fetch(url, { signal: controller.signal });
  clearTimeout(timeout);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  ```
- Go (context + timeout):
  ```go
  ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
  defer cancel()
  req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
  resp, err := http.DefaultClient.Do(req)
  ```
- Rust (reqwest timeout):
  ```rust
  let client = reqwest::Client::builder()
      .timeout(std::time::Duration::from_secs(10))
      .build()?;
  let resp = client.get(url).send().await?.error_for_status()?;
  ```

## Commit & Pull Request Guidelines
- Commit messages in history use short, imperative phrases (e.g., `Add AttackIQ CLI scaffold`).
- Keep commits scoped to one logical change.
- PRs should include: a brief summary, testing notes (`pytest` or `ruff`), and links to relevant issues.
- If the change affects output or UX, include example commands or screenshots.

## Security & Configuration Tips
- Do not log or commit tokens. Use env vars like `ATTACKIQ_ACCOUNT_TOKEN` and `ATTACKIQ_JWT`.
- Keep TLS verification enabled unless explicitly testing `--insecure`.
- Avoid editing `openapi.yaml` unless you intend to change the bundled schema.
- Dependency governance: keep dependency ranges narrow, ship a pinned constraints/lock file for releases, and run `pip-audit` before publishing.

## Agent Governance Docs
- Governance hub: `docs/GOVERNANCE.md`
- Session bootstrap deep-dive workflow: `docs/SESSION_BOOTSTRAP.md`
- Sub-agent scope and response format: `docs/sub-agent-scope.md`
- Session bootstrap: use `docs/SESSION_BOOTSTRAP.md` to compare code, CLI help, and docs before
  changing public documentation.

## Local Agent Skills
- Skills index: `skills/README.md`
- CLI command creation: `skills/cli-command-creation.md`
- API pagination + export patterns: `skills/api-pagination-export.md`
- Security reviews/redaction: `skills/security-review-redaction.md`
- Documentation updates: `skills/documentation-updates.md`

## Shared Snippets
- Location: `scripts/snippets/` (documented in `docs/agent-snippets.md` and `scripts/snippets/README.md`)

## Contribution Reference
- Contributor guide: `CONTRIBUTING.md`
