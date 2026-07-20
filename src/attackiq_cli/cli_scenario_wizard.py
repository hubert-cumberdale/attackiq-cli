from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from attackiq_cli.mutations import write_json_payload
from attackiq_cli.scenario_wizard import (
    ScenarioWizardError,
    apply_scenario_wizard_create,
    apply_scenario_wizard_package,
    build_runtime_prepare_from_image_tar_plan,
    build_runtime_prepare_plan,
    build_scenario_wizard_create_plan,
    build_scenario_wizard_package_plan,
    inspect_scenario_wizard_zip,
    prepare_runtime_bundle_from_bundle,
    prepare_runtime_bundle_from_image_tar,
    scenario_wizard_cache_dir,
    validate_runtime_bundle,
)

console = Console()

scenario_wizard_app = typer.Typer(
    help="Scenario Wizard local workflow helpers.",
    pretty_exceptions_show_locals=False,
)
scenario_wizard_runtime_app = typer.Typer(
    help="Inspect and prepare Scenario Wizard runtimes.",
    pretty_exceptions_show_locals=False,
)
scenario_wizard_app.add_typer(scenario_wizard_runtime_app, name="runtime")

__all__ = [
    "inspect_scenario_wizard_runtime",
    "package_scenario_wizard_scenario",
    "plan_scenario_wizard_create",
    "prepare_scenario_wizard_runtime",
    "scenario_wizard_app",
    "scenario_wizard_runtime_app",
    "validate_scenario_wizard_runtime",
]


def _write_json_to_output(output: Path | None, payload: Any) -> None:
    write_json_payload(
        output,
        payload,
        on_file_written=lambda path: console.print(f"Response written to {path}"),
    )


@scenario_wizard_runtime_app.command("inspect")
def inspect_scenario_wizard_runtime(
    zip_path: Annotated[
        Path,
        typer.Option(
            "--zip",
            help="Scenario Wizard wrapper zip to inspect.",
        ),
    ],
    cache_dir: Annotated[
        Path | None,
        typer.Option(
            "--cache-dir",
            help="Scenario Wizard runtime cache root (defaults to user cache).",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for inspection JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Inspect Scenario Wizard wrapper metadata and local runtime bundle status."""
    try:
        payload = inspect_scenario_wizard_zip(zip_path, cache_dir=cache_dir)
    except ScenarioWizardError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    payload["default_cache_dir"] = str(scenario_wizard_cache_dir())
    _write_json_to_output(output, payload)


@scenario_wizard_runtime_app.command("validate")
def validate_scenario_wizard_runtime(
    bundle: Annotated[
        Path,
        typer.Option(
            "--bundle",
            help="Scenario Wizard runtime bundle directory to validate.",
        ),
    ],
    wizard_version: Annotated[
        str | None,
        typer.Option(
            "--wizard-version",
            help="Expected Scenario Wizard wrapper version.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for validation JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Validate a local Scenario Wizard runtime bundle manifest and required files."""
    payload = validate_runtime_bundle(bundle, expected_wizard_version=wizard_version)
    _write_json_to_output(output, payload)
    if not payload["valid"]:
        raise typer.Exit(code=1)


@scenario_wizard_runtime_app.command("prepare")
def prepare_scenario_wizard_runtime(
    from_bundle: Annotated[
        Path | None,
        typer.Option(
            "--from-bundle",
            help="Validated Scenario Wizard runtime bundle directory to copy into the local cache.",
        ),
    ] = None,
    from_image_tar: Annotated[
        Path | None,
        typer.Option(
            "--from-image-tar",
            help="Docker image filesystem/save tar to convert into a runtime bundle.",
        ),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option(
            "--cache-dir",
            help="Scenario Wizard runtime cache root (defaults to user cache).",
        ),
    ] = None,
    wizard_version: Annotated[
        str | None,
        typer.Option(
            "--wizard-version",
            help="Expected Scenario Wizard wrapper version and destination cache key.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Replace an existing cached runtime bundle at the destination path.",
        ),
    ] = False,
    runtime_root: Annotated[
        str | None,
        typer.Option(
            "--runtime-root",
            help="Path inside image tar containing scenario_wizard.sh (auto-detected by default).",
        ),
    ] = None,
    wheelhouse_path: Annotated[
        str | None,
        typer.Option(
            "--wheelhouse-path",
            help="Path inside image tar containing runtime wheels (auto-detected by default).",
        ),
    ] = None,
    requirements_path: Annotated[
        str | None,
        typer.Option(
            "--requirements-path",
            help=(
                "Path inside image tar containing runtime requirements "
                "(auto-detected by default)."
            ),
        ),
    ] = None,
    python_version: Annotated[
        str,
        typer.Option(
            "--python-version",
            help="Python version target to record in image-tar runtime manifests.",
        ),
    ] = "3.12",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--apply",
            help="Preview by default; --apply copies the validated bundle into the cache.",
        ),
    ] = True,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for prepare plan/result JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Prepare a local Scenario Wizard runtime bundle from explicit trusted artifacts."""
    source_count = int(from_bundle is not None) + int(from_image_tar is not None)
    if source_count != 1:
        raise typer.BadParameter("Provide exactly one source: --from-bundle or --from-image-tar.")
    if dry_run:
        if from_bundle is not None:
            payload = build_runtime_prepare_plan(
                from_bundle,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
            )
        else:
            assert from_image_tar is not None
            payload = build_runtime_prepare_from_image_tar_plan(
                from_image_tar,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
                runtime_root=runtime_root,
                wheelhouse_path=wheelhouse_path,
                requirements_path=requirements_path,
                python_version=python_version,
            )
        _write_json_to_output(output, payload)
        if not payload["ready"]:
            raise typer.Exit(code=1)
        return
    try:
        if from_bundle is not None:
            payload = prepare_runtime_bundle_from_bundle(
                from_bundle,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
            )
        else:
            assert from_image_tar is not None
            payload = prepare_runtime_bundle_from_image_tar(
                from_image_tar,
                cache_dir=cache_dir,
                wizard_version=wizard_version,
                force=force,
                runtime_root=runtime_root,
                wheelhouse_path=wheelhouse_path,
                requirements_path=requirements_path,
                python_version=python_version,
            )
    except ScenarioWizardError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _write_json_to_output(output, payload)
    if not payload["prepared"]:
        raise typer.Exit(code=1)


@scenario_wizard_app.command("create")
def plan_scenario_wizard_create(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Scenario Wizard scenario_configuration.json file.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Directory where Scenario Wizard would create the generated scenario.",
        ),
    ],
    runtime_bundle: Annotated[
        Path,
        typer.Option(
            "--runtime-bundle",
            help="Validated local Scenario Wizard runtime bundle directory.",
        ),
    ],
    wizard_version: Annotated[
        str | None,
        typer.Option(
            "--wizard-version",
            help="Expected Scenario Wizard wrapper version.",
        ),
    ] = None,
    python_executable: Annotated[
        str,
        typer.Option(
            "--python",
            help="Python executable planned for the local Scenario Wizard virtual environment.",
        ),
    ] = "python3.12",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Allow the plan to target an existing generated scenario path.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--apply",
            help="Preview by default; --apply runs the validated local runtime.",
        ),
    ] = True,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="Timeout in seconds for each local create subprocess.",
        ),
    ] = 300.0,
    plan_output: Annotated[
        Path | None,
        typer.Option(
            "--plan-output",
            help="Destination file for dry-run plan or apply result JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Plan or run a no-container Scenario Wizard create flow."""
    if timeout <= 0:
        raise typer.BadParameter("timeout must be greater than zero.")
    if not dry_run:
        try:
            payload = apply_scenario_wizard_create(
                config,
                output_dir,
                runtime_bundle,
                expected_wizard_version=wizard_version,
                force=force,
                python_executable=python_executable,
                timeout_seconds=timeout,
            )
        except ScenarioWizardError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        _write_json_to_output(plan_output, payload)
        if not payload["created"]:
            raise typer.Exit(code=1)
        return
    payload = build_scenario_wizard_create_plan(
        config,
        output_dir,
        runtime_bundle,
        expected_wizard_version=wizard_version,
        force=force,
        python_executable=python_executable,
    )
    _write_json_to_output(plan_output, payload)
    if not payload["ready"]:
        raise typer.Exit(code=1)


@scenario_wizard_app.command("package")
def package_scenario_wizard_scenario(
    scenario: Annotated[
        Path,
        typer.Option(
            "--scenario",
            help="Generated Scenario Wizard scenario directory to package.",
        ),
    ],
    python_executable: Annotated[
        str,
        typer.Option(
            "--python",
            help="Python executable used when a scenario-local virtualenv must be created.",
        ),
    ] = "python3.12",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Allow packaging when target zip files already exist.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--apply",
            help="Preview by default; --apply runs local packaging.",
        ),
    ] = True,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="Timeout in seconds for each local package subprocess.",
        ),
    ] = 300.0,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Destination file for package plan or result JSON (defaults to stdout).",
        ),
    ] = None,
) -> None:
    """Plan or run local packaging for a generated Scenario Wizard scenario."""
    if timeout <= 0:
        raise typer.BadParameter("timeout must be greater than zero.")
    if dry_run:
        payload = build_scenario_wizard_package_plan(
            scenario,
            force=force,
            python_executable=python_executable,
        )
        _write_json_to_output(output, payload)
        if not payload["ready"]:
            raise typer.Exit(code=1)
        return
    try:
        payload = apply_scenario_wizard_package(
            scenario,
            force=force,
            python_executable=python_executable,
            timeout_seconds=timeout,
        )
    except ScenarioWizardError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _write_json_to_output(output, payload)
    if not payload["packaged"]:
        raise typer.Exit(code=1)
