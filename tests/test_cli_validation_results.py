from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_validation_results as cli_validation_results
from attackiq_cli.config import CliConfig


class DummySpecIndex:
    pass


def _patch_validation_results_config(monkeypatch) -> None:
    monkeypatch.setattr(cli_validation_results, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_validation_results,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(
        cli_validation_results,
        "warn_if_insecure_base_url",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        cli_validation_results.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )


def test_validation_results_list_passes_filters(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_validation_results(
        _context,
        *,
        by_asset,
        page,
        page_size,
        filters,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "by_asset": by_asset,
                "page": page,
                "page_size": page_size,
                "filters": filters,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"scenario_id": "scenario-1", "validated": 3}], False

    _patch_validation_results_config(monkeypatch)
    monkeypatch.setattr(
        cli_validation_results,
        "svc_fetch_validation_results",
        _fetch_validation_results,
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "validation-results",
            "list",
            "--days",
            "7",
            "--project-ids",
            " project-1,project-2 ",
            "--scope-id",
            " scope-1 ",
            "--tag-ids",
            " tag-1 ",
            "--page",
            "2",
            "--page-size",
            "10",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == [{"scenario_id": "scenario-1", "validated": 3}]
    assert captured["by_asset"] is False
    assert captured["page"] == 2
    assert captured["page_size"] == 10
    assert captured["filters"].days == 7
    assert captured["filters"].project_ids == "project-1,project-2"
    assert captured["filters"].scope_id == "scope-1"
    assert captured["filters"].tag_ids == "tag-1"
    assert captured["insecure"] is False
    assert captured["timeout"] == 5.0


def test_validation_results_by_asset_writes_csv(tmp_path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_validation_results(
        _context,
        *,
        by_asset,
        page,
        page_size,
        filters,
        insecure,
        timeout,
    ):
        _ = filters, insecure, timeout
        captured.update({"by_asset": by_asset, "page": page, "page_size": page_size})
        return [{"asset_id": "asset-1", "validated": 4}], True

    output = tmp_path / "validation-by-asset.csv"
    _patch_validation_results_config(monkeypatch)
    monkeypatch.setattr(
        cli_validation_results,
        "svc_fetch_validation_results",
        _fetch_validation_results,
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "validation-results",
            "by-asset",
            "--output-format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured == {"by_asset": True, "page": 1, "page_size": 200}
    assert output.read_text(encoding="utf-8").splitlines() == [
        "asset_id,validated",
        "asset-1,4",
    ]


def test_validation_results_asset_executions_passes_asset_id(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_validation_result_executions(
        _context,
        *,
        asset_id,
        scenario_id,
        filters,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "asset_id": asset_id,
                "scenario_id": scenario_id,
                "filters": filters,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"scenario_id": "scenario-1", "execution_count": 2}]

    _patch_validation_results_config(monkeypatch)
    monkeypatch.setattr(
        cli_validation_results,
        "svc_fetch_validation_result_executions",
        _fetch_validation_result_executions,
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "validation-results",
            "asset-executions",
            " asset-1 ",
            "--days",
            "30",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == [{"scenario_id": "scenario-1", "execution_count": 2}]
    assert captured["asset_id"] == "asset-1"
    assert captured["scenario_id"] is None
    assert captured["filters"].days == 30


def test_validation_results_scenario_executions_passes_scenario_id(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_validation_result_executions(
        _context,
        *,
        asset_id,
        scenario_id,
        filters,
        insecure,
        timeout,
    ):
        _ = filters, insecure, timeout
        captured.update({"asset_id": asset_id, "scenario_id": scenario_id})
        return [{"asset_id": "asset-1", "execution_count": 2}]

    _patch_validation_results_config(monkeypatch)
    monkeypatch.setattr(
        cli_validation_results,
        "svc_fetch_validation_result_executions",
        _fetch_validation_result_executions,
    )

    result = CliRunner().invoke(
        cli.app,
        ["validation-results", "scenario-executions", " scenario-1 "],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == [{"asset_id": "asset-1", "execution_count": 2}]
    assert captured == {"asset_id": None, "scenario_id": "scenario-1"}


def test_validation_results_rejects_invalid_paging_and_days(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_validation_results,
        "load_config_or_exit",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    bad_page = runner.invoke(cli.app, ["validation-results", "list", "--page", "0"])
    bad_days = runner.invoke(
        cli.app,
        ["validation-results", "asset-executions", "asset-1", "--days", "0"],
    )

    assert bad_page.exit_code != 0
    assert bad_days.exit_code != 0
    assert "page must be >= 1" in bad_page.output
    assert "days must be >= 1" in bad_days.output


def test_validation_results_reports_malformed_payload(monkeypatch) -> None:
    def _fetch_validation_results(*_args, **_kwargs):
        raise ValueError("Validation results response must contain a results list or be a list.")

    _patch_validation_results_config(monkeypatch)
    monkeypatch.setattr(
        cli_validation_results,
        "svc_fetch_validation_results",
        _fetch_validation_results,
    )

    result = CliRunner().invoke(cli.app, ["validation-results", "list"])

    assert result.exit_code == 1
    assert "Validation results response must contain a results list or be a list." in result.output
