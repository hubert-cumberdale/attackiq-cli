from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

import pytest

import attackiq_cli.backup as backup
import attackiq_cli.backup_catalog as backup_catalog
from attackiq_cli.client import AttackIQClient
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
    def __init__(self, responses: dict[str, list[dict[str, Any]]]):
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def send(self, operation: Operation, *, query_params, **_kwargs) -> ResponseStub:
        self.calls.append((operation.operation_id, dict(query_params)))
        payloads = self.responses[operation.operation_id]
        if not payloads:
            raise AssertionError(f"Unexpected call for {operation.operation_id}")
        return ResponseStub(payloads.pop(0))


class ClientManager:
    def __init__(self, client: ClientStub):
        self.client = client

    def __enter__(self) -> ClientStub:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> Literal[False]:
        return False


def _options(output_dir: Path, *, include: str | None = None) -> backup.ConfigBackupOptions:
    return backup.ConfigBackupOptions(
        output_dir=output_dir,
        domains=backup.normalize_backup_domains(include),
        page_size=100,
        max_pages=None,
        company_id=None,
        endpoint_catalog=None,
        tenant_alias="tenant-a",
        command="attackiq backup configs",
        insecure=False,
        timeout=None,
    )


def test_redact_backup_payload_redacts_nested_secrets_and_preserves_mapping_fields() -> None:
    payload = {
        "records": [
            {
                "id": "rule-1",
                "name": "Rule One",
                "mapping": {"source_field": "hostname", "target_field": "asset"},
                "configuration": {"password": "raw-password", "host": "example.com"},
                "metadata": {
                    "api_token": "raw-token",
                    "download_url": "https://example.com/file?sig=raw-signature",
                },
                "certificate": "-----BEGIN CERTIFICATE-----\nraw-cert\n-----END CERTIFICATE-----",
                "rule_content": "title: keep benign detection content",
            }
        ]
    }

    redacted, report = backup.redact_backup_payload(payload)
    encoded = json.dumps(redacted, sort_keys=True)

    assert report.redacted_count == 4
    assert "raw-password" not in encoded
    assert "raw-token" not in encoded
    assert "raw-signature" not in encoded
    assert "raw-cert" not in encoded
    assert "hostname" in encoded
    assert "keep benign detection content" in encoded


def test_run_configuration_backup_writes_redacted_artifacts_and_manifest(
    monkeypatch, tmp_path
) -> None:
    client = ClientStub(
        {
            "v1_company_connectors_list": [
                {
                    "results": [
                        {
                            "id": "company-connector-1",
                            "display_name": "Sentinel",
                            "company": {"id": "company-1", "name": "Tenant"},
                            "connector": {"id": "connector-1", "name": "Connector"},
                            "configuration": {"client_secret": "integration-secret"},
                        }
                    ],
                    "next": None,
                }
            ],
            "v1_source_types_list": [
                {
                    "results": [
                        {
                            "id": "source-type-1",
                            "name": "Alert",
                            "api_token": "source-secret",
                        }
                    ],
                    "next": None,
                }
            ],
            "v1_unified_mitigations_with_relations_list": [
                {
                    "results": [
                        {
                            "id": "rule-1",
                            "name": "Detection Rule",
                            "content": "title: keep rule content",
                            "signed_url": "https://example.com/rule?X-Amz-Signature=secret",
                        }
                    ],
                    "next": None,
                }
            ],
        }
    )
    monkeypatch.setattr(backup, "build_client", lambda *_args, **_kwargs: ClientManager(client))

    manifest = backup.run_configuration_backup(_context(), _options(tmp_path / "backup"))

    assert {artifact["domain"] for artifact in manifest["artifacts"]} == {
        "integrations",
        "source-types",
        "detection-rules",
    }
    assert (
        "v1_source_types_list",
        {"page": 1, "page_size": 100, "company": "company-1", "connector": "connector-1"},
    ) in client.calls
    for path in (tmp_path / "backup").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "integration-secret" not in text
        assert "source-secret" not in text
        assert "X-Amz-Signature=secret" not in text
    assert "keep rule content" in (tmp_path / "backup" / "detection-rules.json").read_text(
        encoding="utf-8"
    )


def test_fetch_paginated_records_rejects_malformed_results() -> None:
    client = ClientStub(
        {
            "v1_company_connectors_list": [
                {"results": {"id": "connector-1"}, "next": None},
            ]
        }
    )

    with pytest.raises(backup.BackupError, match="results must be a list"):
        backup.fetch_paginated_records(
            cast(AttackIQClient, client),
            _operation("v1_company_connectors_list", "/v1/company_connectors"),
            page_size=100,
            max_pages=None,
            response_label="Integration connector list",
        )


def test_fetch_paginated_records_respects_max_pages() -> None:
    client = ClientStub(
        {
            "v1_company_connectors_list": [
                {"results": [{"id": "connector-1"}], "next": "page-2"},
                {"results": [{"id": "connector-2"}], "next": None},
            ]
        }
    )

    records = backup.fetch_paginated_records(
        cast(AttackIQClient, client),
        _operation("v1_company_connectors_list", "/v1/company_connectors"),
        page_size=100,
        max_pages=1,
        response_label="Integration connector list",
    )

    assert records == [{"id": "connector-1"}]
    assert len(client.calls) == 1


def test_endpoint_catalog_rejects_write_like_backup_entries() -> None:
    catalog = {
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

    entries = {entry.domain: entry for entry in backup_catalog.validate_endpoint_catalog(catalog)}
    with pytest.raises(backup.BackupError, match="write-like"):
        backup_catalog.validate_requested_domains(("tenant-sso",), entries)


def test_endpoint_catalog_example_validates() -> None:
    example_path = Path("docs/CONFIGURATION_BACKUP_ENDPOINT_CATALOG.example.json")
    entries = backup_catalog.validate_endpoint_catalog(
        json.loads(example_path.read_text(encoding="utf-8"))
    )

    assert {entry.domain for entry in entries} == {
        "observable-field-mappings",
        "tenant-sso-settings",
    }


def test_catalog_needs_redaction_fails_on_unclassified_sensitive_field(tmp_path) -> None:
    output_dir = backup.prepare_backup_output_dir(tmp_path / "catalog-backup")

    with pytest.raises(backup.BackupError, match="unclassified sensitive fields"):
        backup.write_backup_artifact(
            output_dir=output_dir,
            domain="tenant-sso",
            operation_id="endpoint-catalog:/v1/sso",
            source="endpoint-catalog",
            classification="needs-redaction",
            records=[{"id": "sso-1", "client_secret": "raw-secret"}],
            sensitive_fields=("api_token",),
            fail_on_unclassified=True,
        )
