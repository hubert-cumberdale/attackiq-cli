from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_QUALITY_GATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quality_gate.py"
_QUALITY_GATE_SPEC = importlib.util.spec_from_file_location("quality_gate", _QUALITY_GATE_PATH)
assert _QUALITY_GATE_SPEC is not None
assert _QUALITY_GATE_SPEC.loader is not None
quality_gate = importlib.util.module_from_spec(_QUALITY_GATE_SPEC)
sys.modules[_QUALITY_GATE_SPEC.name] = quality_gate
_QUALITY_GATE_SPEC.loader.exec_module(quality_gate)


def test_quality_gate_build_commands_default():
    commands = quality_gate.build_commands()
    names = [command.name for command in commands]

    assert names == [
        "dependency constraints",
        "release governance",
        "public safety",
        "secret scan",
        "public mirror dry run",
        "AIQ Assist MCP provider contract",
        "AIQ Assist MCP fixtures",
        "CLI command-tree contract",
        "GA CLI inventory parity",
        "architecture boundaries",
        "ruff",
        "mypy",
        "pytest",
        "doc links",
        "mkdocs",
    ]
    assert commands[0].argv == [sys.executable, "scripts/check_dependency_constraints.py"]
    assert commands[1].argv == [sys.executable, "scripts/check_release_governance.py"]
    assert commands[2].argv == [sys.executable, "scripts/check_public_safety.py"]
    assert commands[3].argv == [sys.executable, "scripts/check_secret_scan.py"]
    assert commands[4].argv == [
        sys.executable,
        "scripts/check_public_mirror.py",
        "--allow-dirty",
        "--skip-wheel",
    ]
    assert commands[5].argv == [sys.executable, "scripts/check_aiq_assist_mcp_contract.py"]
    assert commands[6].argv == [sys.executable, "scripts/check_aiq_assist_mcp_fixtures.py"]
    assert commands[7].argv == [
        sys.executable,
        "scripts/render_cli_contract.py",
        "--check",
    ]
    assert commands[8].argv == [
        sys.executable,
        "scripts/check_ga_cli_inventory.py",
    ]
    assert commands[9].argv == [
        sys.executable,
        "scripts/deterministic_review.py",
        "--check-architecture",
    ]
    assert commands[10].argv == [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "src",
        "tests",
        "scripts/quality_gate.py",
        "scripts/build_enterprise_package.py",
        "scripts/build_artifactory_promotion_evidence.py",
        "scripts/build_signing_attestation_evidence.py",
        "scripts/verify_enterprise_evidence.py",
        "scripts/verify_enterprise_package.py",
        "scripts/package_provenance.py",
        "scripts/package_sbom.py",
        "scripts/package_dependency_integrity.py",
        "scripts/check_secret_scan.py",
        "scripts/check_public_mirror.py",
        "scripts/check_public_safety.py",
        "scripts/check_release_governance.py",
        "scripts/check_aiq_assist_mcp_contract.py",
        "scripts/check_aiq_assist_mcp_fixtures.py",
        "scripts/render_cli_contract.py",
        "scripts/check_ga_cli_inventory.py",
        "scripts/deterministic_review.py",
        "scripts/live_smoke.py",
    ]
    assert commands[-1].argv == [sys.executable, "-m", "mkdocs", "build"]


def test_quality_gate_build_commands_can_skip_mkdocs():
    commands = quality_gate.build_commands(include_mkdocs=False)

    assert [command.name for command in commands] == [
        "dependency constraints",
        "release governance",
        "public safety",
        "secret scan",
        "public mirror dry run",
        "AIQ Assist MCP provider contract",
        "AIQ Assist MCP fixtures",
        "CLI command-tree contract",
        "GA CLI inventory parity",
        "architecture boundaries",
        "ruff",
        "mypy",
        "pytest",
        "doc links",
    ]


def test_quality_gate_dry_run(capsys):
    result = quality_gate.main(["--dry-run", "--no-mkdocs"])

    assert result == 0
    output = capsys.readouterr().out
    assert "==> ruff:" in output
    assert "quality gate passed" in output
