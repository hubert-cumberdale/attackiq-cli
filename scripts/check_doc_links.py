from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".ruff_cache"}

# Filenames that are referenced but intentionally outside this repo.
EXTERNAL_REFERENCES = {"SKILL.md"}


def iter_markdown_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("*.md"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def resolve_reference(ref: str) -> tuple[bool, str | None]:
    if ref in EXTERNAL_REFERENCES:
        return True, None
    if "*" in ref:
        return True, None
    if ref.startswith("http://") or ref.startswith("https://"):
        return True, None
    if ref.startswith("/"):
        return True, None

    direct = (REPO_ROOT / ref).resolve()
    if direct.exists():
        return True, None

    name = Path(ref).name
    if name in EXTERNAL_REFERENCES:
        return True, None

    matches = [p for p in REPO_ROOT.rglob(name) if all(part not in EXCLUDE_DIRS for part in p.parts)]
    if not matches:
        return False, "missing"

    if len(matches) == 1:
        return True, None

    preferred = [m for m in matches if "src" in m.parts]
    if len(preferred) == 1:
        return True, None

    return False, "ambiguous"


def main() -> int:
    pattern = re.compile(r"`([^`]+\.(?:md|py|yaml))`")
    missing: list[str] = []
    ambiguous: list[str] = []

    for doc in iter_markdown_files():
        text = doc.read_text()
        for ref in pattern.findall(text):
            ok, reason = resolve_reference(ref)
            if not ok and reason == "missing":
                missing.append(f"{doc.relative_to(REPO_ROOT)}: {ref}")
            elif not ok and reason == "ambiguous":
                ambiguous.append(f"{doc.relative_to(REPO_ROOT)}: {ref}")

    if missing:
        print("Missing referenced files:")
        for item in missing:
            print(f"- {item}")
    if ambiguous:
        print("Ambiguous references:")
        for item in ambiguous:
            print(f"- {item}")

    if missing or ambiguous:
        return 1

    print("All referenced files exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
