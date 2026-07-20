from __future__ import annotations

import json

import pytest

from attackiq_cli import backup_artifacts
from attackiq_cli.backup_catalog import BackupError


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

    redacted, report = backup_artifacts.redact_backup_payload(payload)
    encoded = json.dumps(redacted, sort_keys=True)

    assert report.redacted_count == 4
    assert "raw-password" not in encoded
    assert "raw-token" not in encoded
    assert "raw-signature" not in encoded
    assert "raw-cert" not in encoded
    assert "hostname" in encoded
    assert "keep benign detection content" in encoded


def test_write_backup_artifact_redacts_payload_and_returns_summary(tmp_path) -> None:
    summary = backup_artifacts.write_backup_artifact(
        output_dir=tmp_path,
        domain="Tenant SSO",
        operation_id="endpoint-catalog:/v1/sso",
        source="endpoint-catalog",
        classification="needs-redaction",
        records=[{"id": "sso-1", "client_secret": "raw-secret"}],
        sensitive_fields=("client_secret",),
        fail_on_unclassified=True,
    )

    artifact_text = (tmp_path / "tenant-sso.json").read_text(encoding="utf-8")
    assert "raw-secret" not in artifact_text
    assert backup_artifacts.REDACTED_VALUE in artifact_text
    assert summary["artifact"] == "tenant-sso.json"
    assert summary["redaction_status"] == "redacted"
    assert summary["redacted_paths"] == ["$.records[0].client_secret"]


def test_write_backup_artifact_rejects_unclassified_catalog_secret(tmp_path) -> None:
    with pytest.raises(BackupError, match="unclassified sensitive fields"):
        backup_artifacts.write_backup_artifact(
            output_dir=tmp_path,
            domain="tenant-sso",
            operation_id="endpoint-catalog:/v1/sso",
            source="endpoint-catalog",
            classification="needs-redaction",
            records=[{"id": "sso-1", "client_secret": "raw-secret"}],
            sensitive_fields=("api_token",),
            fail_on_unclassified=True,
        )
