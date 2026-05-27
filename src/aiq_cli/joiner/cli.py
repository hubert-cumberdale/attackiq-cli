"""Compatibility entrypoint for aiq_cli.joiner.cli."""

from __future__ import annotations

from attackiq_cli.joiner.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

