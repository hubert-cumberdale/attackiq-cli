from __future__ import annotations

import json
from typing import Any, Literal, cast

from typer.testing import CliRunner

import attackiq_cli.backup as backup
import attackiq_cli.cli as cli
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ServiceContext, build_auth_context
from attackiq_cli.spec import Operation, SpecIndex


def _operation(operation_id: str, path: str) -> Operation:
    return Operation(
        operation_id=operation_id,
        method="get",
        path=path,
        summary="",
        parameters=[],
        request_body=None,
        tags=[],
        security=[],
    )


class SpecStub:
    def get_operation(self, operation_id: str) -> Operation:
        paths = {
            "v1_company_connectors_list": "/v1/company_connectors",
            "v1_source_types_list": "/v1/source_types",
            "v1_unified_mitigations_with_relations_list": "/v1/unified_mitigations_with_relations",
        }
        return _operation(operation_id, paths[operation_id])


def _context() -> ServiceContext:
    return ServiceContext(
        config=CliConfig(),
        base_url="https://api.example.com",
        auth=build_auth_context(CliConfig(), preferred_scheme="none"),
        spec=cast(SpecIndex, SpecStub()),
    )


class ResponseStub:
    def __init__(self, payload: Any):
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class ClientStub:
    def send(
        self,
        operation: Operation,
        *,
        query_params: dict[str, Any],
        **_kwargs,
    ) -> ResponseStub:
        _ = query_params
        if operation.operation_id == "v1_company_connectors_list":
            return ResponseStub(
                {
                    "results": [
                        {
                            "id": "company-connector-1",
                            "display_name": "Sentinel",
                            "company": {"id": "company-1"},
                            "connector": {"id": "connector-1"},
                            "configuration": {"password": "raw-secret"},
                        }
                    ],
                    "next": None,
                }
            )
        raise AssertionError(f"Unexpected operation: {operation.operation_id}")


class ClientManager:
    def __enter__(self) -> ClientStub:
        return ClientStub()

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False


def test_backup_configs_passes_options_to_runner(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    def _run_configuration_backup(_context, options: backup.ConfigBackupOptions):
        captured["options"] = options
        return {"artifacts": []}

    monkeypatch.setattr(
        cli,
        "_prepare_read_only_context",
        lambda *_args, **_kwargs: (_context(), 5.0),
    )
    monkeypatch.setattr(cli, "run_configuration_backup", _run_configuration_backup)

    result = CliRunner().invoke(
        cli.app,
        [
            "backup",
            "configs",
            "--output-dir",
            str(tmp_path / "backup"),
            "--include",
            "integrations,source-types",
            "--page-size",
            "50",
            "--max-pages",
            "2",
            "--company-id",
            "11111111-1111-4111-8111-111111111111",
            "--tenant-alias",
            "tenant-a",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    options = captured["options"]
    assert options.domains == ("integrations", "source-types")
    assert options.page_size == 50
    assert options.max_pages == 2
    assert options.company_id == "11111111-1111-4111-8111-111111111111"
    assert options.tenant_alias == "tenant-a"
    assert options.timeout == 5.0


def test_backup_configs_refuses_repo_output_path(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "_prepare_read_only_context",
        lambda *_args, **_kwargs: (_context(), None),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "backup",
            "configs",
            "--output-dir",
            "repo-local-backup",
            "--include",
            "integrations",
        ],
    )

    assert result.exit_code == 1
    assert "outside the git worktree" in result.output


def test_backup_configs_rejects_write_like_catalog_domain(monkeypatch, tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "version": 1,
                "endpoints": [
                    {
                        "domain": "tenant-sso",
                        "method": "POST",
                        "path": "/v1/sso",
                        "classification": "write-like",
                        "pagination": "none",
                        "response_kind": "object",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "_prepare_read_only_context",
        lambda *_args, **_kwargs: (_context(), None),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "backup",
            "configs",
            "--output-dir",
            str(tmp_path / "backup"),
            "--include",
            "tenant-sso",
            "--endpoint-catalog",
            str(catalog_path),
        ],
    )

    assert result.exit_code == 1
    assert "write-like" in result.output


def test_backup_configs_redacts_files_and_terminal(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        cli,
        "_prepare_read_only_context",
        lambda *_args, **_kwargs: (_context(), None),
    )
    monkeypatch.setattr(backup, "build_client", lambda *_args, **_kwargs: ClientManager())

    result = CliRunner().invoke(
        cli.app,
        [
            "backup",
            "configs",
            "--output-dir",
            str(tmp_path / "backup"),
            "--include",
            "integrations",
        ],
    )

    assert result.exit_code == 0
    assert "raw-secret" not in result.output
    artifact_text = (tmp_path / "backup" / "integrations.json").read_text(encoding="utf-8")
    manifest_text = (tmp_path / "backup" / "manifest.json").read_text(encoding="utf-8")
    assert "raw-secret" not in artifact_text
    assert "raw-secret" not in manifest_text
    assert "[REDACTED]" in artifact_text
