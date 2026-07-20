from __future__ import annotations

import json
import re
from typing import Any

from typer.testing import CliRunner

import attackiq_cli.cli as cli
import attackiq_cli.cli_results as cli_results
from attackiq_cli.config import CliConfig
from attackiq_cli.services import ResultsMode


class DummySpecIndex:
    pass


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _patch_results_config(monkeypatch) -> None:
    monkeypatch.setattr(cli_results, "load_config_or_exit", lambda: CliConfig())
    monkeypatch.setattr(
        cli_results,
        "resolve_base_url",
        lambda *_args, **_kwargs: "https://api.example.com",
    )
    monkeypatch.setattr(cli_results, "warn_if_insecure_base_url", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        cli_results.SpecIndex,
        "from_file",
        lambda *_args, **_kwargs: DummySpecIndex(),
    )


def test_results_list_defaults_to_summary_mode(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_results_list(
        _context,
        *,
        mode,
        page,
        page_size,
        search,
        tag_id,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "mode": mode,
                "page": page,
                "page_size": page_size,
                "search": search,
                "tag_id": tag_id,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"id": "result-1", "name": "Assessment run"}], False

    _patch_results_config(monkeypatch)
    monkeypatch.setattr(cli_results, "svc_fetch_results_list", _fetch_results_list)

    result = CliRunner().invoke(cli.app, ["results", "list"])

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == [{"id": "result-1", "name": "Assessment run"}]
    assert captured == {
        "mode": ResultsMode.SUMMARIES,
        "page": 1,
        "page_size": 200,
        "search": None,
        "tag_id": None,
        "insecure": False,
        "timeout": None,
    }


def test_results_list_summaries_passes_tag_id(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_results_list(
        _context,
        *,
        mode,
        page,
        page_size,
        search,
        tag_id,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "mode": mode,
                "page": page,
                "page_size": page_size,
                "search": search,
                "tag_id": tag_id,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"id": "result-1"}], False

    _patch_results_config(monkeypatch)
    monkeypatch.setattr(cli_results, "svc_fetch_results_list", _fetch_results_list)

    result = CliRunner().invoke(
        cli.app,
        ["results", "list", "--mode", "summaries", "--tag-id", " tag-1 "],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["mode"] == ResultsMode.SUMMARIES
    assert captured["tag_id"] == "tag-1"


def test_results_list_phases_csv_passes_search_and_paging(tmp_path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_results_list(
        _context,
        *,
        mode,
        page,
        page_size,
        search,
        tag_id,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "mode": mode,
                "page": page,
                "page_size": page_size,
                "search": search,
                "tag_id": tag_id,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"id": "phase-1", "name": "Credential check"}], True

    output = tmp_path / "phases.csv"
    _patch_results_config(monkeypatch)
    monkeypatch.setattr(cli_results, "svc_fetch_results_list", _fetch_results_list)

    result = CliRunner().invoke(
        cli.app,
        [
            "results",
            "list",
            "--mode",
            "phases",
            "--search",
            " credential ",
            "--page",
            "2",
            "--page-size",
            "10",
            "--timeout",
            "5",
            "--output-format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured == {
        "mode": ResultsMode.PHASES,
        "page": 2,
        "page_size": 10,
        "search": "credential",
        "tag_id": None,
        "insecure": False,
        "timeout": 5.0,
    }
    assert output.read_text(encoding="utf-8").splitlines() == [
        "id,name",
        "phase-1,Credential check",
    ]


def test_results_list_rejects_tag_id_for_phases(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_results,
        "load_config_or_exit",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )

    result = CliRunner().invoke(
        cli.app,
        ["results", "list", "--mode", "phases", "--tag-id", "tag-1"],
    )

    assert result.exit_code != 0
    assert "tag-id is only supported for summaries mode" in result.output


def test_results_phases_requires_one_join_key(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_results,
        "load_config_or_exit",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )

    runner = CliRunner()
    missing = runner.invoke(cli.app, ["results", "phases"])
    both = runner.invoke(
        cli.app,
        [
            "results",
            "phases",
            "--result-summary-id",
            "summary-1",
            "--scenario-job-id",
            "job-1",
        ],
    )

    assert missing.exit_code != 0
    assert both.exit_code != 0
    assert "Provide exactly one" in missing.output
    assert "Provide exactly one" in both.output


def test_results_phases_fetches_by_result_summary_id(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_phase_results(
        _context,
        *,
        result_summary_id,
        scenario_job_id,
        page,
        page_size,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "result_summary_id": result_summary_id,
                "scenario_job_id": scenario_job_id,
                "page": page,
                "page_size": page_size,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"id": "phase-1", "status": "passed"}]

    _patch_results_config(monkeypatch)
    monkeypatch.setattr(cli_results, "svc_fetch_phase_results", _fetch_phase_results)

    result = CliRunner().invoke(
        cli.app,
        [
            "results",
            "phases",
            "--result-summary-id",
            " summary-1 ",
            "--page",
            "3",
            "--page-size",
            "25",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == [{"id": "phase-1", "status": "passed"}]
    assert captured == {
        "result_summary_id": "summary-1",
        "scenario_job_id": None,
        "page": 3,
        "page_size": 25,
        "insecure": False,
        "timeout": None,
    }


def test_results_logs_fetches_by_scenario_job_id_csv(tmp_path, monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fetch_phase_logs(
        _context,
        *,
        result_summary_id,
        scenario_job_id,
        page,
        page_size,
        insecure,
        timeout,
    ):
        captured.update(
            {
                "result_summary_id": result_summary_id,
                "scenario_job_id": scenario_job_id,
                "page": page,
                "page_size": page_size,
                "insecure": insecure,
                "timeout": timeout,
            }
        )
        return [{"scenario_job_id": "job-1", "message": "ok"}]

    output = tmp_path / "logs.csv"
    _patch_results_config(monkeypatch)
    monkeypatch.setattr(cli_results, "svc_fetch_phase_logs", _fetch_phase_logs)

    result = CliRunner().invoke(
        cli.app,
        [
            "results",
            "logs",
            "--scenario-job-id",
            " job-1 ",
            "--output-format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured == {
        "result_summary_id": None,
        "scenario_job_id": "job-1",
        "page": 1,
        "page_size": 200,
        "insecure": False,
        "timeout": None,
    }
    assert output.read_text(encoding="utf-8").splitlines() == [
        "message,scenario_job_id",
        "ok,job-1",
    ]


def test_results_rejects_invalid_mode_before_loading_config(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_results,
        "load_config_or_exit",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )

    result = CliRunner().invoke(cli.app, ["results", "list", "--mode", "unknown"])

    assert result.exit_code != 0
    assert "mode must be one of" in result.output


def test_results_csv_requires_output_before_loading_config(monkeypatch) -> None:
    monkeypatch.setattr(
        cli_results,
        "load_config_or_exit",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )

    result = CliRunner().invoke(cli.app, ["results", "list", "--output-format", "csv"])

    assert result.exit_code != 0
    assert "CSV output requires --output" in _strip_ansi(result.output)
