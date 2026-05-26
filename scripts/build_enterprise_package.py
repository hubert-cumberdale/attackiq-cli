#!/usr/bin/env python3
"""Build validated enterprise package artifacts from a public release tag."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    import tomli as tomllib  # type: ignore[no-redef]

try:
    from scripts import check_public_safety as public_safety
    from scripts import package_provenance
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback.
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import check_public_safety as public_safety  # type: ignore[no-redef]
    import package_provenance  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_REPO_URL = "https://github.com/hubert-cumberdale/attackiq-cli.git"
CHECKSUM_FILE_NAME = "SHA256SUMS"
MANIFEST_NAME = "ENTERPRISE_PROMOTION_MANIFEST.json"
PROVENANCE_NAME = package_provenance.PROVENANCE_NAME
RELEASE_REF_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")


def _run(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def ensure_output_dir(path: Path, *, root: Path = ROOT) -> Path:
    output_dir = path.expanduser().resolve()
    repo_root = root.resolve()
    if output_dir == repo_root or is_relative_to(output_dir, repo_root):
        raise RuntimeError("enterprise package output directory must be outside the source repo")
    if output_dir.exists() and not output_dir.is_dir():
        raise RuntimeError(f"enterprise package output path is not a directory: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"enterprise package output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def validate_source_ref(source_ref: str) -> str:
    match = RELEASE_REF_RE.fullmatch(source_ref)
    if not match:
        raise RuntimeError("enterprise packages must be built from a vX.Y.Z release tag")
    return match.group("version")


def validate_public_repo_url(public_repo_url: str) -> None:
    parsed = urlparse(public_repo_url)
    if parsed.username or parsed.password:
        raise RuntimeError("public repo URL must not include embedded credentials")


def clone_source(public_repo_url: str, source_ref: str, destination: Path) -> None:
    validate_public_repo_url(public_repo_url)
    _run(
        [
            "git",
            "clone",
            "--branch",
            source_ref,
            "--depth",
            "1",
            public_repo_url,
            str(destination),
        ],
        cwd=ROOT,
    )


def resolve_source_commit(source_dir: Path) -> str:
    completed = _run(["git", "rev-parse", "HEAD"], cwd=source_dir)
    return completed.stdout.strip()


def load_package_version(source_dir: Path) -> str:
    data = tomllib.loads((source_dir / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def validate_package_version(source_ref: str, package_version: str) -> None:
    expected_version = validate_source_ref(source_ref)
    if package_version != expected_version:
        raise RuntimeError(
            f"package version mismatch: source_ref={source_ref}, pyproject={package_version}"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256s(output_dir: Path, hashes: dict[str, str]) -> Path:
    checksum_path = output_dir / CHECKSUM_FILE_NAME
    lines = [f"{digest}  {filename}" for filename, digest in sorted(hashes.items())]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def build_promotion_manifest(
    *,
    public_repo_url: str,
    source_ref: str,
    source_commit: str,
    package_version: str,
    wheel_filename: str,
    wheel_sha256: str,
    build_created_utc: str,
    provenance_filename: str = PROVENANCE_NAME,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "public_repo_url": public_repo_url,
        "source_ref": source_ref,
        "source_commit": source_commit,
        "package_version": package_version,
        "build_created_utc": build_created_utc,
        "python_version": sys.version.split()[0],
        "artifacts": [
            {
                "filename": wheel_filename,
                "sha256": wheel_sha256,
                "type": "wheel",
            }
        ],
        "checksum_file": CHECKSUM_FILE_NAME,
        "provenance_file": provenance_filename,
        "package_policy": "validated wheel for enterprise package repository promotion",
        "artifactory_policy": "upload is operator-owned; credentials are not accepted or stored",
        "sbom_policy": (
            "offline package provenance and dependency inventory are generated; "
            "registry signing and attestation remain operator-owned"
        ),
        "validation_commands": [
            f"python3 scripts/build_enterprise_package.py --source-ref {source_ref} "
            "--output-dir <dir>",
            "python3 scripts/verify_enterprise_package.py <dir>",
            "python3 scripts/check_public_safety.py",
            "python -m pip install -c constraints.txt <wheel>",
            "attackiq --version",
            "attackiq config validate",
        ],
    }


def write_manifest(output_dir: Path, manifest: dict[str, Any]) -> Path:
    manifest_path = output_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def build_validated_wheel(source_dir: Path, output_dir: Path) -> tuple[Path, str]:
    source_errors = public_safety.scan_tracked_files(source_dir)
    if source_errors:
        raise RuntimeError("public source safety scan failed:\n- " + "\n- ".join(source_errors))

    with tempfile.TemporaryDirectory(prefix="attackiq-cli-enterprise-wheel-") as tmpdir:
        wheel_path = public_safety.build_wheel(Path(tmpdir), root=source_dir)
        wheel_errors = public_safety.scan_wheel(wheel_path)
        if wheel_errors:
            raise RuntimeError(
                "enterprise wheel safety scan failed:\n- " + "\n- ".join(wheel_errors)
            )
        target_path = output_dir / wheel_path.name
        shutil.copy2(wheel_path, target_path)

    return target_path, sha256_file(target_path)


def build_enterprise_package(
    *,
    source_ref: str,
    output_dir: Path,
    public_repo_url: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    validate_source_ref(source_ref)
    validate_public_repo_url(public_repo_url)
    artifact_dir = ensure_output_dir(output_dir, root=root)

    with tempfile.TemporaryDirectory(prefix="attackiq-cli-enterprise-source-") as tmpdir:
        source_dir = Path(tmpdir) / "source"
        clone_source(public_repo_url, source_ref, source_dir)
        source_commit = resolve_source_commit(source_dir)
        package_version = load_package_version(source_dir)
        validate_package_version(source_ref, package_version)
        wheel_path, wheel_sha256 = build_validated_wheel(source_dir, artifact_dir)

    manifest = build_promotion_manifest(
        public_repo_url=public_repo_url,
        source_ref=source_ref,
        source_commit=source_commit,
        package_version=package_version,
        wheel_filename=wheel_path.name,
        wheel_sha256=wheel_sha256,
        build_created_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    manifest_path = write_manifest(artifact_dir, manifest)
    provenance = package_provenance.build_package_provenance(
        package_dir=artifact_dir,
        manifest=manifest,
        manifest_filename=MANIFEST_NAME,
        wheel_path=wheel_path,
        wheel_sha256=wheel_sha256,
        checksum_filename=CHECKSUM_FILE_NAME,
    )
    provenance_path = package_provenance.write_package_provenance(artifact_dir, provenance)
    provenance_sha256 = sha256_file(provenance_path)
    checksum_path = write_sha256s(
        artifact_dir,
        {
            wheel_path.name: wheel_sha256,
            provenance_path.name: provenance_sha256,
        },
    )

    return {
        "output_dir": artifact_dir,
        "public_repo_url": public_repo_url,
        "source_ref": source_ref,
        "source_commit": source_commit,
        "package_version": package_version,
        "wheel_path": wheel_path,
        "wheel_sha256": wheel_sha256,
        "checksum_path": checksum_path,
        "manifest_path": manifest_path,
        "provenance_path": provenance_path,
        "provenance_sha256": provenance_sha256,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-ref",
        required=True,
        help="Public release tag to build, in vX.Y.Z form.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Empty directory outside the repo for generated package artifacts.",
    )
    parser.add_argument(
        "--public-repo-url",
        default=DEFAULT_PUBLIC_REPO_URL,
        help=f"Public source mirror URL. Defaults to {DEFAULT_PUBLIC_REPO_URL}.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        summary = build_enterprise_package(
            source_ref=args.source_ref,
            output_dir=args.output_dir,
            public_repo_url=args.public_repo_url,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print("Enterprise package build failed:", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            if exc.stdout:
                print(exc.stdout, file=sys.stderr)
            if exc.stderr:
                print(exc.stderr, file=sys.stderr)
        return 1

    print("Enterprise package build OK.")
    print(f"Output directory: {summary['output_dir']}")
    print(f"Public source: {summary['public_repo_url']}")
    print(f"Source ref: {summary['source_ref']}")
    print(f"Source commit: {summary['source_commit']}")
    print(f"Package version: {summary['package_version']}")
    print(f"Wheel: {summary['wheel_path']}")
    print(f"Wheel SHA256: {summary['wheel_sha256']}")
    print(f"Checksums: {summary['checksum_path']}")
    print(f"Promotion manifest: {summary['manifest_path']}")
    print(f"Package provenance: {summary['provenance_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
