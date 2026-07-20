#!/usr/bin/env python3
"""Build and validate an offline SPDX JSON SBOM for enterprise package directories."""

from __future__ import annotations

import email
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SBOM_NAME = "ENTERPRISE_PACKAGE_SBOM.spdx.json"
SBOM_DOCUMENT_TYPE = "attackiq-cli-enterprise-package-sbom"
SPDX_VERSION = "SPDX-2.3"


def _read_wheel_metadata(wheel_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(wheel_path) as wheel:
        metadata_names = [
            name
            for name in wheel.namelist()
            if name.endswith(".dist-info/METADATA") and not name.startswith("/")
        ]
        if len(metadata_names) != 1:
            raise RuntimeError(
                f"expected exactly one wheel METADATA file in {wheel_path.name}, "
                f"found {len(metadata_names)}"
            )
        metadata_text = wheel.read(metadata_names[0]).decode("utf-8")

    message = email.message_from_string(metadata_text)
    return {
        "name": message.get("Name", ""),
        "version": message.get("Version", ""),
        "dependencies": sorted(message.get_all("Requires-Dist") or []),
    }


def _dependency_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    return match.group(1).lower().replace("_", "-") if match else requirement


def _dependency_version_info(requirement: str) -> str:
    name = _dependency_name(requirement)
    rest = requirement[len(name) :].strip() if requirement.lower().startswith(name) else ""
    return rest or "NOASSERTION"


def _spdx_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-")
    return f"SPDXRef-{normalized or 'package'}"


def _package_url(name: str, version: str | None = None) -> str:
    normalized = name.lower().replace("_", "-")
    if version and version != "NOASSERTION":
        return f"pkg:pypi/{normalized}@{version}"
    return f"pkg:pypi/{normalized}"


def build_package_sbom(
    *,
    manifest: dict[str, Any],
    wheel_path: Path,
    wheel_sha256: str,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Create a public-safe SPDX JSON SBOM for a built enterprise package."""

    generated = generated_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    package_version = str(manifest.get("package_version") or "")
    source_ref = str(manifest.get("source_ref") or "")
    source_commit = str(manifest.get("source_commit") or "")
    metadata = _read_wheel_metadata(wheel_path)
    root_name = str(metadata.get("name") or "attackiq-cli")
    root_version = str(metadata.get("version") or package_version)
    root_spdx_id = _spdx_id(f"Package-{root_name}")

    packages: list[dict[str, Any]] = [
        {
            "name": root_name,
            "SPDXID": root_spdx_id,
            "versionInfo": root_version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "checksums": [{"algorithm": "SHA256", "checksumValue": wheel_sha256}],
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": _package_url(root_name, root_version),
                }
            ],
            "supplier": "NOASSERTION",
        }
    ]
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_spdx_id,
        }
    ]

    for requirement in metadata.get("dependencies", []):
        dependency_name = _dependency_name(str(requirement))
        dependency_spdx_id = _spdx_id(f"Dependency-{dependency_name}")
        packages.append(
            {
                "name": dependency_name,
                "SPDXID": dependency_spdx_id,
                "versionInfo": _dependency_version_info(str(requirement)),
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": _package_url(dependency_name),
                    }
                ],
                "supplier": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": root_spdx_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_spdx_id,
            }
        )

    return {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"attackiq-cli-enterprise-package-{package_version}",
        "documentNamespace": (
            "https://attackiq-cli.local/sbom/"
            f"{source_ref.strip('/') or package_version}/{source_commit or 'unknown'}"
        ),
        "creationInfo": {
            "created": generated,
            "creators": ["Tool: attackiq-cli enterprise package builder"],
        },
        "documentDescribes": [root_spdx_id],
        "packages": packages,
        "relationships": relationships,
        "annotations": [
            {
                "annotationType": "OTHER",
                "annotator": "Tool: attackiq-cli enterprise package builder",
                "annotationDate": generated,
                "comment": SBOM_DOCUMENT_TYPE,
            }
        ],
    }


def write_package_sbom(package_dir: Path, sbom: dict[str, Any]) -> Path:
    sbom_path = package_dir / SBOM_NAME
    sbom_path.write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sbom_path


def load_package_sbom(sbom_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{SBOM_NAME}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{SBOM_NAME}: expected JSON object"]
    return data, []


def validate_package_sbom(
    *,
    manifest: dict[str, Any],
    sbom: dict[str, Any],
    sbom_filename: str,
) -> list[str]:
    errors: list[str] = []
    if sbom_filename != SBOM_NAME:
        errors.append(f"{SBOM_NAME}: unexpected SBOM filename")
    if sbom.get("spdxVersion") != SPDX_VERSION:
        errors.append(f"{SBOM_NAME}: spdxVersion must be {SPDX_VERSION}")
    if sbom.get("SPDXID") != "SPDXRef-DOCUMENT":
        errors.append(f"{SBOM_NAME}: SPDXID must be SPDXRef-DOCUMENT")
    creation_info = sbom.get("creationInfo")
    if not isinstance(creation_info, dict) or not isinstance(creation_info.get("created"), str):
        errors.append(f"{SBOM_NAME}: creationInfo.created must be a string")

    packages = sbom.get("packages")
    if not isinstance(packages, list) or not packages:
        return errors + [f"{SBOM_NAME}: packages must be a non-empty list"]

    root_packages = [
        package
        for package in packages
        if isinstance(package, dict) and package.get("name") == "attackiq-cli"
    ]
    if len(root_packages) != 1:
        errors.append(f"{SBOM_NAME}: exactly one attackiq-cli package is required")
        return errors
    root = root_packages[0]
    if root.get("versionInfo") != manifest.get("package_version"):
        errors.append(f"{SBOM_NAME}: attackiq-cli versionInfo must match package_version")

    artifacts = manifest.get("artifacts")
    wheel_digest = None
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict) and artifact.get("type") == "wheel":
                wheel_digest = artifact.get("sha256")
                break
    checksums = root.get("checksums")
    root_digest = None
    if isinstance(checksums, list):
        for checksum in checksums:
            if isinstance(checksum, dict) and checksum.get("algorithm") == "SHA256":
                root_digest = checksum.get("checksumValue")
                break
    if wheel_digest is not None and root_digest != wheel_digest:
        errors.append(f"{SBOM_NAME}: attackiq-cli SHA256 must match wheel artifact")

    relationships = sbom.get("relationships")
    if not isinstance(relationships, list):
        errors.append(f"{SBOM_NAME}: relationships must be a list")
    return errors
