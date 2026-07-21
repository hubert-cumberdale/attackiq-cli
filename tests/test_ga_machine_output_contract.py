from __future__ import annotations

import csv
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
from typer.testing import CliRunner

import attackiq_cli.backup as backup
import attackiq_cli.cli as cli
from attackiq_cli.catalog import (
    CATALOG_CSV_FIELDS,
    BasCatalog,
    build_catalog_coverage_summary,
    catalog_records_for_csv,
    normalize_catalog_records,
)
from attackiq_cli.cli_call import handle_response
from attackiq_cli.exporter import (
    ASSESSMENT_FIELD_ORDER,
    ASSET_FIELD_ORDER,
    SCENARIO_EXPORT_FIELDS,
    SCENARIO_FIELD_ORDER,
    TEMPLATE_CSV_HEADER,
    TEMPLATE_FIELD_ORDER,
    TEST_FIELD_ORDER,
    build_scenario_export_records,
    write_csv_records,
    write_json,
)
from attackiq_cli.joiner.cli import JoinOptions, run_join
from attackiq_cli.joiner.det_pipeline import DetPipelineOptions, run_det_pipeline
from attackiq_cli.mutations import build_dry_run_call_plan, write_dry_run_call_plan
from attackiq_cli.scenario_wizard import (
    build_runtime_prepare_from_image_tar_plan,
    build_runtime_prepare_plan,
    build_scenario_wizard_create_plan,
    build_scenario_wizard_package_plan,
)
from attackiq_cli.service_core import ServiceContext
from attackiq_cli.tui_exports import build_tui_export_path, write_tui_export

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CONTRACT_PATH = FIXTURES / "ga_machine_output_contract.json"
GA_CONTRACT_PATH = ROOT / "docs" / "GA_STABLE_CONTRACT.md"


def _contract() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(CONTRACT_PATH.read_text(encoding="utf-8")),
    )


def _sorted_keys(value: dict[str, Any]) -> list[str]:
    return sorted(value)


def _assert_plan_shape(plan: dict[str, Any], expected: dict[str, Any]) -> None:
    assert _sorted_keys(plan) == expected["keys"]
    assert {
        action["name"]: _sorted_keys(action)
        for action in plan["planned_actions"]
    } == expected["action_keys"]


def _catalog_fixture() -> BasCatalog:
    scenario = {
        "id": "AWS-DRV-CLOUD-IAM-TOKEN-ABUSE-T1550-FIXTURE",
        "title": "Synthetic token validation",
        "status": "proposed",
        "cloud_provider": "aws",
        "domain": "DRV-CLOUD",
        "surface": "IAM",
        "pattern": "TOKEN-ABUSE",
        "scenario_type": "ATOMIC",
        "provider_execution_classification": "custom_harness_only",
        "attackiq_support": "custom_harness_only",
        "bas_suitability_score": 3,
        "mitre": {"technique": "T1550", "tactics": ["Lateral Movement"]},
        "execution": {"cleanup_required": True},
        "detections": {
            "aws": {
                "event_names": ["GetSessionToken"],
                "logs": ["CloudTrail"],
            }
        },
        "safety": {
            "destructive": False,
            "production_safe": False,
            "cost_risk": "low",
        },
        "required_permissions": ["sts:GetSessionToken"],
        "references": {},
        "catalog_tags": ["synthetic"],
        "provider_extension": {"future": True},
        "_path": "synthetic/catalog-scenario.yml",
    }
    inventory = [
        {
            "attack_id": "T1550",
            "attack_name": "Use Alternate Authentication Material",
            "tactics": ["Lateral Movement"],
            "bas_simulation_status": "partial",
        }
    ]
    return BasCatalog(
        root=Path("synthetic-catalog"),
        scenarios=[scenario],
        inventory=inventory,
        flat_catalog=None,
    )


def _write_det_pipeline_inputs(root: Path) -> tuple[Path, Path]:
    issues = root / "det-issues.csv"
    with issues.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["IID", "Title", "Description", "Labels"])
        writer.writeheader()
        writer.writerow(
            {
                "IID": "1",
                "Title": "Synthetic script detection",
                "Description": "## Detection Mapping\nTechnique T1059",
                "Labels": "tool::SplunkES,DET1234,T1059",
            }
        )

    scenarios = root / "det-scenarios.csv"
    with scenarios.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "name", "scenario_tags", "supported_platform"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "scenario-fixture-1",
                "name": "Synthetic script execution",
                "scenario_tags": "T1059",
                "supported_platform": "Windows",
            }
        )
    return issues, scenarios


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_contract_fixture_covers_every_task_six_output_family() -> None:
    contract = _contract()

    assert contract["schema_version"] == 1
    assert set(contract) == {
        "backup",
        "build_payloads",
        "catalog",
        "common_records",
        "dedicated_dry_run_call_plan",
        "exports",
        "extension_policy",
        "generic_call_formats",
        "join",
        "scenario_wizard_plans",
        "schema_version",
        "tui_exports",
    }
    assert contract["extension_policy"] == {
        "raw_provider_records": "allow-additional-fields",
        "repository_owned_envelopes": "exact-keys",
    }

    documented = GA_CONTRACT_PATH.read_text(encoding="utf-8")
    task_six = documented.split("6. Completed:", maxsplit=1)[1].split(
        "\n7. Completed:", maxsplit=1
    )[0]
    assert "tests/fixtures/ga_machine_output_contract.json" in task_six
    assert "tests/test_ga_machine_output_contract.py" in task_six
    assert (
        "8. Completed: GitHub Actions runs the contract suite and full quality-gate-equivalent "
        "checks on\n   Python 3.10 through 3.13"
        in documented
    )


def test_common_json_and_csv_keep_provider_extensions_without_owning_them(
    tmp_path: Path,
) -> None:
    common = _contract()["common_records"]
    records = common["synthetic_input"]
    record = records[0]

    assert set(record) >= set(common["required_record_keys"])

    json_output = tmp_path / "records.json"
    write_json(json_output, records)
    assert json.loads(json_output.read_text(encoding="utf-8")) == records
    assert json_output.read_text(encoding="utf-8") == json.dumps(
        records,
        indent=2,
        sort_keys=True,
    ) + "\n"

    csv_output = tmp_path / "records.csv"
    write_csv_records(csv_output, records, preferred_fields=common["preferred_fields"])
    with csv_output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == common["csv_headers"]
    assert rows[1][-2:] == ["retained", '{"future": true}']


def test_dedicated_dry_run_call_plan_is_an_exact_repository_envelope(
    tmp_path: Path,
) -> None:
    expected = _contract()["dedicated_dry_run_call_plan"]
    actual = build_dry_run_call_plan(
        operation_id=expected["operation_id"],
        path_params=expected["path_params"],
        query_params=expected["query_params"],
        json_body=expected["json_body"],
    )

    assert actual == expected

    output = tmp_path / "call-plan.json"
    write_dry_run_call_plan(output=output, **expected)
    assert json.loads(output.read_text(encoding="utf-8")) == expected


def test_build_payload_shapes_match_the_machine_contract() -> None:
    expected = _contract()["build_payloads"]
    commands = {
        "assessment_from_template": [
            "build",
            "assessment",
            "from-template",
            "--template-id",
            expected["assessment_from_template"]["template"],
            "--name",
            expected["assessment_from_template"]["project_name"],
            "--blueprint-id",
            expected["assessment_from_template"]["blueprint"],
        ],
        "test_create": [
            "build",
            "test",
            "create",
            "--assessment-id",
            expected["test_create"]["project"],
            "--name",
            expected["test_create"]["name"],
        ],
        "test_add_scenarios": [
            "build",
            "test",
            "add-scenarios",
            "03fef867-3227-4d47-a858-90f9ad8cf217",
            "--scenario-id",
            expected["test_add_scenarios"]["include"][0],
            "--scenario-id",
            expected["test_add_scenarios"]["include"][1],
        ],
    }

    runner = CliRunner()
    for name, argv in commands.items():
        result = runner.invoke(cli.app, argv)
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == expected[name]


def test_generic_call_pretty_json_raw_and_csv_formats_are_frozen(tmp_path: Path) -> None:
    expected = _contract()["generic_call_formats"]

    pretty_output = tmp_path / "pretty.json"
    handle_response(
        httpx.Response(
            200,
            json={
                "id": "provider-record-1",
                "provider_extra": {"future": True},
            },
        ),
        pretty_output,
        "pretty-json",
    )
    assert pretty_output.read_text(encoding="utf-8") == expected["pretty_json"]

    raw_output = tmp_path / "raw.txt"
    handle_response(
        httpx.Response(
            200,
            text=expected["raw"],
            headers={"content-type": "text/plain"},
        ),
        raw_output,
        "raw",
    )
    assert raw_output.read_text(encoding="utf-8") == expected["raw"]

    csv_output = tmp_path / "call.csv"
    handle_response(
        httpx.Response(
            200,
            json=[{"id": 1, "name": "alpha", "provider_extra": "retained"}],
        ),
        csv_output,
        "csv",
    )
    assert csv_output.read_text(encoding="utf-8") == expected["csv"]


def test_export_shapes_freeze_owned_projections_and_allow_raw_extensions(
    tmp_path: Path,
) -> None:
    expected = _contract()["exports"]["field_orders"]
    assert expected == {
        "assessments": ASSESSMENT_FIELD_ORDER,
        "scenarios": SCENARIO_EXPORT_FIELDS,
        "template_rows": TEMPLATE_CSV_HEADER,
        "templates": TEMPLATE_FIELD_ORDER,
        "tests": TEST_FIELD_ORDER,
    }

    provider_records = [
        {
            "id": "scenario-1",
            "name": "Synthetic scenario",
            "scenario_type": "atomic",
            "description": "Synthetic description",
            "created": "2026-07-21T00:00:00Z",
            "modified": "2026-07-21T01:00:00Z",
            "cancellable": True,
            "capabilities": [{"display_name": "Synthetic capability"}],
            "last_updated": "2026-07-21T01:00:00Z",
            "description_json": {
                "failure_criteria": "Synthetic failure",
                "prerequisites": "Synthetic prerequisite",
                "prevention_criteria": "Synthetic prevention",
            },
            "scenario_tags": [{"tag": {"display_name": "Synthetic tag"}}],
            "supported_platforms": {"windows": "10"},
            "provider_extension": {"future": True},
        }
    ]

    raw_json = tmp_path / "scenarios.json"
    write_json(raw_json, provider_records)
    assert json.loads(raw_json.read_text(encoding="utf-8"))[0]["provider_extension"] == {
        "future": True
    }

    normalized = build_scenario_export_records(provider_records)
    assert _sorted_keys(normalized[0]) == sorted(expected["scenarios"])
    assert "provider_extension" not in normalized[0]

    csv_output = tmp_path / "scenarios.csv"
    write_csv_records(
        csv_output,
        normalized,
        preferred_fields=SCENARIO_EXPORT_FIELDS,
        include_preferred_missing=True,
        include_other_fields=False,
    )
    with csv_output.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == expected["scenarios"]


def test_backup_artifact_and_manifest_envelopes_are_frozen(
    tmp_path: Path,
    monkeypatch,
) -> None:
    expected = _contract()["backup"]
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    summary = backup.write_backup_artifact(
        output_dir=artifact_dir,
        domain="synthetic-domain",
        operation_id="v1_synthetic_list",
        source="openapi",
        classification="needs-redaction",
        records=[
            {
                "id": "record-1",
                "provider_extension": {"future": True},
                "client_secret": "synthetic-secret-placeholder",
            }
        ],
    )
    artifact = json.loads((artifact_dir / "synthetic-domain.json").read_text(encoding="utf-8"))

    assert _sorted_keys(summary) == expected["artifact_summary_keys"]
    assert _sorted_keys(artifact) == expected["artifact_payload_keys"]
    assert artifact["records"][0]["provider_extension"] == {"future": True}
    assert artifact["records"][0]["client_secret"] == backup.REDACTED_VALUE

    monkeypatch.setattr(backup, "utc_timestamp", lambda: "2026-07-21T12:00:00Z")
    monkeypatch.setattr(
        backup,
        "build_client",
        lambda *_args, **_kwargs: nullcontext(object()),
    )
    context = cast(
        ServiceContext,
        SimpleNamespace(
            base_url="https://synthetic.example.test",
            config=object(),
            auth=object(),
        ),
    )
    manifest = backup.run_configuration_backup(
        context,
        backup.ConfigBackupOptions(
            output_dir=tmp_path / "backup",
            domains=(),
            page_size=5,
            max_pages=1,
            company_id=None,
            endpoint_catalog=None,
            tenant_alias="synthetic-tenant",
            command="attackiq backup configs",
            insecure=False,
            timeout=10.0,
        ),
    )

    assert _sorted_keys(manifest) == expected["manifest_keys"]
    assert _sorted_keys(manifest["redaction_policy"]) == expected["redaction_policy_keys"]
    assert json.loads(
        (tmp_path / "backup" / "manifest.json").read_text(encoding="utf-8")
    ) == manifest


def test_join_artifact_names_headers_and_manifest_are_frozen(tmp_path: Path) -> None:
    expected = _contract()["join"]
    join_fixtures = FIXTURES / "joiner"
    outdir = tmp_path / "joined"
    run_join(
        JoinOptions(
            assessments=join_fixtures / "assessments.csv",
            scenarios=join_fixtures / "scenarios.csv",
            issues=join_fixtures / "issues.csv",
            outdir=outdir,
            timestamp="2026-07-21T12:00:00Z",
            fail_on_missing_scenario=True,
            fail_on_malformed_scenario_technique=True,
        )
    )

    assert sorted(path.name for path in outdir.iterdir()) == sorted(expected["output_files"])
    for filename, headers in expected["csv_headers"].items():
        with (outdir / filename).open(newline="", encoding="utf-8") as handle:
            assert next(csv.reader(handle)) == headers

    manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
    assert _sorted_keys(manifest) == expected["manifest_keys"]
    assert _sorted_keys(manifest["options"]) == expected["manifest_option_keys"]
    for entry in [*manifest["inputs"], *manifest["outputs"]]:
        assert _sorted_keys(entry) == expected["hash_entry_keys"]


def test_det_pipeline_dry_run_artifact_envelopes_are_frozen(tmp_path: Path) -> None:
    expected = _contract()["join"]["det_pipeline"]
    issues, scenarios = _write_det_pipeline_inputs(tmp_path)
    outdir = tmp_path / "det-output"

    report = run_det_pipeline(
        DetPipelineOptions(
            issues=issues,
            scenarios=scenarios,
            outdir=outdir,
            project_id="synthetic-project",
            apply=False,
            dry_run=True,
        )
    )
    artifacts = outdir / "artifacts"

    assert sorted(path.name for path in artifacts.iterdir()) == expected["output_files"]
    assert _sorted_keys(report) == expected["apply_report_keys"]
    for filename, headers in expected["csv_headers"].items():
        with (artifacts / filename).open(newline="", encoding="utf-8") as handle:
            assert next(csv.reader(handle)) == headers

    manifest = json.loads((artifacts / "manifest.json").read_text(encoding="utf-8"))
    assert _sorted_keys(manifest) == expected["manifest_keys"]
    for entry in [*manifest["inputs"], *manifest["outputs"]]:
        assert _sorted_keys(entry) == expected["manifest_entry_keys"]

    normalized = _read_jsonl(artifacts / "issues_normalized.jsonl")
    assert _sorted_keys(normalized[0]) == expected["normalized_issue_keys"]

    reconciliation = json.loads(
        (artifacts / "technique_reconciliation.json").read_text(encoding="utf-8")
    )
    recommendations = json.loads(
        (artifacts / "recommendations.json").read_text(encoding="utf-8")
    )
    assessment_plan = json.loads(
        (artifacts / "assessment_plan.json").read_text(encoding="utf-8")
    )
    patch_plan = json.loads(
        (artifacts / "gitlab_patch_plan.json").read_text(encoding="utf-8")
    )
    for envelope in (reconciliation, recommendations, assessment_plan, patch_plan):
        assert _sorted_keys(envelope) == expected["item_envelope_keys"]

    assert _sorted_keys(reconciliation["items"][0]) == expected[
        "reconciliation_item_keys"
    ]
    recommendation_group = recommendations["items"][0]
    assert _sorted_keys(recommendation_group) == expected["recommendations_item_keys"]
    recommendation = recommendation_group["recommendations"][0]
    assert _sorted_keys(recommendation) == expected["recommendation_keys"]
    assert _sorted_keys(recommendation["score_breakdown"]) == expected[
        "score_breakdown_keys"
    ]
    assert _sorted_keys(assessment_plan["items"][0]) == expected[
        "assessment_plan_item_keys"
    ]
    assert _sorted_keys(patch_plan["items"][0]) == expected["patch_plan_item_keys"]

    requests = _read_jsonl(artifacts / "attackiq_create_requests.ndjson")
    assert _sorted_keys(requests[0]) == expected["request_keys"]
    assert _sorted_keys(requests[0]["payload"]) == expected["request_payload_keys"]
    previews = _read_jsonl(artifacts / "gitlab_description_previews.jsonl")
    assert _sorted_keys(previews[0]) == expected["preview_keys"]


def test_catalog_record_coverage_and_csv_shapes_are_frozen() -> None:
    expected = _contract()["catalog"]
    catalog = _catalog_fixture()
    records = normalize_catalog_records(catalog)
    coverage = build_catalog_coverage_summary(catalog)
    csv_records = catalog_records_for_csv(records)

    assert _sorted_keys(records[0]) == expected["record_keys"]
    assert "provider_extension" not in records[0]
    assert _sorted_keys(coverage) == expected["coverage_keys"]
    assert _sorted_keys(coverage["techniques"][0]) == expected["technique_keys"]
    assert list(CATALOG_CSV_FIELDS) == expected["csv_headers"]
    assert _sorted_keys(csv_records[0]) == sorted(expected["csv_headers"])


def test_scenario_wizard_dry_run_plan_envelopes_are_frozen(tmp_path: Path) -> None:
    expected = _contract()["scenario_wizard_plans"]
    missing_runtime = tmp_path / "missing-runtime"

    _assert_plan_shape(
        build_runtime_prepare_plan(
            missing_runtime,
            cache_dir=tmp_path / "cache",
            wizard_version="0.0.3",
        ),
        expected["runtime_prepare"],
    )
    _assert_plan_shape(
        build_runtime_prepare_from_image_tar_plan(
            tmp_path / "missing-image.tar",
            cache_dir=tmp_path / "image-cache",
            wizard_version="0.0.3",
        ),
        expected["runtime_prepare_image_tar"],
    )
    _assert_plan_shape(
        build_scenario_wizard_create_plan(
            tmp_path / "missing-config.json",
            tmp_path / "generated",
            missing_runtime,
            expected_wizard_version="0.0.3",
        ),
        expected["create"],
    )
    _assert_plan_shape(
        build_scenario_wizard_package_plan(tmp_path / "missing-scenario"),
        expected["package"],
    )


def test_tui_export_paths_and_domain_field_orders_are_frozen(tmp_path: Path) -> None:
    expected = _contract()["tui_exports"]
    assert expected["field_orders"] == {
        "assessments": ASSESSMENT_FIELD_ORDER,
        "assets": ASSET_FIELD_ORDER,
        "results_group": [
            "count",
            "join_key",
            "result_summary_id",
            "scenario_job_id",
            "source",
        ],
        "scenarios": SCENARIO_FIELD_ORDER,
        "settings": ["key", "value", "source", "category"],
        "tests": TEST_FIELD_ORDER,
    }

    paged = build_tui_export_path(
        str(tmp_path),
        "scenarios",
        "json",
        page=2,
        timestamp="20260721T120000Z",
    )
    unpaged = build_tui_export_path(
        str(tmp_path),
        "settings",
        "csv",
        timestamp="20260721T120000Z",
    )
    assert paged.relative_to(tmp_path).as_posix() == expected["paged_path"]
    assert unpaged.relative_to(tmp_path).as_posix() == expected["unpaged_path"]

    records = _contract()["common_records"]["synthetic_input"]
    write_tui_export(paged, "json", records)
    assert json.loads(paged.read_text(encoding="utf-8")) == records

    csv_output = tmp_path / "exports" / "provider-records.csv"
    write_tui_export(
        csv_output,
        "csv",
        records,
        preferred_fields=["id", "name"],
    )
    with csv_output.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == _contract()["common_records"]["csv_headers"]
