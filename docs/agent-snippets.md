# Shared Agent Snippets

All reusable snippets live in `scripts/snippets/`.

## Available Snippets
- `scripts/snippets/pagination_helper.py`: reusable pagination loop with httpx.
- `scripts/snippets/cli_command_template.py`: CLI command skeleton with Typer-style patterns.
- `scripts/snippets/snippet_test_template.py`: pytest template for CLI commands or helpers.
- `scripts/snippets/structured_logging.py`: safe structured logging with redaction helper.
- `scripts/snippets/README.md`: usage notes for shared snippets.

## Usage
- Copy the snippet into the target module and adapt names and parameters.
- Keep redaction logic for any user-provided or secret-like data.
- Add tests when integrating a snippet into runtime code.
