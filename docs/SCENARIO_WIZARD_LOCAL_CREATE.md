# Scenario Wizard Local Create Design

This design describes how `aiq-cli` could add a local `create` sequence for AttackIQ Scenario
Wizard without running the Docker container at scenario creation time.

## Current Reality

The local Scenario Wizard zip is a thin wrapper. It contains:

- `Makefile`
- run_script.py
- `README.md`
- `version.txt`
- `pip.conf`

The wrapper creates or adapts a local Python 3.12 virtual environment, but actual scenario creation
is delegated to `scenario_wizard.sh` inside the `attackiq/scenario-wizard` Docker image. Generated
scenario Makefiles also use the image for environment setup and test helpers.

This means `aiq-cli` cannot create scenarios from the zip alone without either:

1. running the Docker image, or
2. having a local runtime bundle extracted or reproduced from that image.

Current implemented support is limited to read-only inspection, runtime bundle validation, and
dry-run-first local runtime preparation/create/package flows:

```bash
attackiq scenario-wizard runtime inspect --zip /path/to/scenario-wizard-0.0.3.zip
attackiq scenario-wizard runtime validate --bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3 --wizard-version 0.0.3
attackiq scenario-wizard runtime prepare --from-bundle /path/to/runtime-bundle --wizard-version 0.0.3
attackiq scenario-wizard runtime prepare --from-image-tar /path/to/scenario-wizard-image.tar --wizard-version 0.0.3
attackiq scenario-wizard create --dry-run --config scenario_configuration.json --output generated-scenarios/ --runtime-bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3
attackiq scenario-wizard create --apply --config scenario_configuration.json --output generated-scenarios/ --runtime-bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3
attackiq scenario-wizard package --dry-run --scenario generated-scenarios/example
attackiq scenario-wizard package --apply --scenario generated-scenarios/example
```

The command reports wrapper metadata, whether the zip appears wrapper-only, and whether the
expected local runtime bundle already exists. Runtime validation checks the manifest and expected
bundle layout. Runtime preparation copies an explicitly supplied prebuilt bundle into the local
cache only when validation passes and `--apply` is used. Create planning emits the exact local
actions that would be taken. Create apply runs those local actions against a validated runtime
bundle, without network calls, Docker, or the image shell entrypoint, and captures bounded redacted
subprocess output.
Package planning and apply use the generated scenario's local packaging path without invoking the
generated Makefile.
Image-tar preparation can turn a trusted exported filesystem tar or Docker-save layer tar into that
same bundle layout without running the container.

The trusted 0.0.3 image has now been inspected from an exported Docker-save tar. The image runtime
includes an internal `make_scenario` module, with the generated scenario output path hard-coded as
`/usr/src/folder` in the image's internal `scenario_params` module. The CLI create path imports
that module directly from the extracted runtime and patches the output path in memory. The
generated scenario `Makefile` packages by creating or reusing a
scenario-local `venv`, installing `requirements.txt` from `.pipdownload`, and then running
Scenario Wizard packaging helpers. The image packaging helper's `p` stage may fall back to PyPI for
missing wheels, so the CLI implementation deliberately replaces that implicit network fallback
with local-only dependency staging.

## Goal

Add a mature, explicit workflow that can run:

```bash
attackiq scenario-wizard runtime inspect --zip /path/to/scenario-wizard-0.0.3.zip
attackiq scenario-wizard runtime prepare --from-bundle /path/to/runtime-bundle --wizard-version 0.0.3 --apply
attackiq scenario-wizard runtime prepare --from-image-tar /path/to/scenario-wizard-image.tar --wizard-version 0.0.3 --apply
attackiq scenario-wizard create --apply --config scenario_configuration.json --output generated-scenarios/ --runtime-bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3
attackiq scenario-wizard package --apply --scenario generated-scenarios/example
```

The create/package steps should not require a running container when a valid local runtime bundle
exists.

## Recommended Architecture

Introduce a versioned local runtime bundle.

```text
~/.cache/attackiq-cli/scenario-wizard/
  0.0.3/
    manifest.json
    wheelhouse/
    runtime/
      scenario_wizard/
        impl/
          make_scenario.py
        templates/
      scenario_wizard.sh   # optional legacy image helper, not used by create apply
    python/
      bin/
        fullrelease
        package
      requirements.lock
      site-packages/
```

The runtime bundle should be treated as generated/private cache, not source code in this repo.

## Command Responsibilities

### `runtime inspect`

Read the Scenario Wizard zip and report:

- wrapper version from `version.txt`
- minimum image version
- whether the zip contains only wrapper files or a full local runtime
- whether a compatible local runtime bundle already exists

This command must not print `pip.conf` contents.

Status: implemented with CLI tests and redaction coverage. The inspection result intentionally
suppresses checksums for sensitive package configuration files because a checksum can still help
confirm the presence of credentialed material across environments.

### `runtime prepare`

Materialize a local runtime bundle. Supported sources should be explicit:

- `--from-bundle <path>`: use a prebuilt internal bundle.
- `--from-image-tar <path>`: unpack a trusted saved Docker image filesystem tar or Docker-save
  layer tar without running a container.
- future `--from-image attackiq/scenario-wizard:<version>`: optionally export image layers through
  Docker, still without running the scenario creation container.

The command should write a manifest with:

- Scenario Wizard wrapper version
- image/runtime version
- source type
- file checksums
- Python version requirement
- wheelhouse hash summary
- creation timestamp

Do not store Docker Hub credentials, `pip.conf`, or browser/session artifacts in the manifest.

Status: implemented for `--from-bundle` and `--from-image-tar`. The command is dry-run by default,
requires exactly one source, and requires `--apply` to write into the versioned cache. Bundle
preparation refuses invalid source bundles, sensitive package configuration files, symlinks,
overlapping source/destination paths, and existing destinations unless `--force` is explicit.
Image-tar preparation supports exported filesystem tar files and Docker-save-style `layer.tar`
archives, auto-detects common runtime paths, and can be directed with `--runtime-root`,
`--wheelhouse-path`, `--requirements-path`, and `--python-version`. It extracts only selected
runtime scripts, templates, wheelhouse files, and requirements, excludes sensitive package config
files such as `pip.conf`, writes a generated manifest, validates the staged bundle, and does not
run Docker.

### `runtime validate`

Validate a prepared runtime bundle before any create flow can use it:

```bash
attackiq scenario-wizard runtime validate --bundle ~/.cache/attackiq-cli/scenario-wizard/0.0.3 --wizard-version 0.0.3
```

Validation checks:

- manifest JSON shape and required fields
- Scenario Wizard wrapper version compatibility
- Python 3.12 runtime target
- runtime create module and templates directory; the legacy image shell entrypoint is reported when
  present but is not required for local create
- wheelhouse and requirements lock presence
- wheelhouse checksum consistency when `wheelhouse_sha256` is declared
- secret-like manifest keys and sensitive package configuration files

Status: implemented. Validation emits JSON and exits non-zero when the bundle is not usable for
local create planning.

### `create`

Given a runtime bundle and a `scenario_configuration.json` file:

1. Validate the configuration JSON.
2. Create an isolated Python 3.12 virtual environment in a throwaway workspace.
3. Install runtime dependencies from the bundle wheelhouse with `--no-index --find-links`.
4. Invoke the local `scenario_wizard.impl.make_scenario` Python module, not Docker.
5. Write generated scenario source into the requested output directory.
6. Emit a JSON result with scenario path, runtime version, and generated files.

If no compatible runtime bundle exists, fail closed with a message that explains how to prepare one.

Current status: dry-run planning, fixture-backed apply execution, and real image-backed execution
are implemented. The command validates the runtime bundle and the minimal Scenario Wizard
configuration contract (`scenario_name`, `scenario_description`, and `phase_description`), rejects
secret-like configuration keys, derives the expected scenario output path, creates a local virtual
environment, links the bundle `runtime/` directory and extracted image site-packages through
`PYTHONPATH`, reads the configuration from a restrictive temporary file, patches the image's
hard-coded `/usr/src/folder` output path in memory, invokes the runtime `make_scenario` Python
module directly, and fails if the expected scenario directory is not produced. For real
image-backed bundles, create copies the extracted wheelhouse into the generated scenario
`.pipdownload` directory and records a private `.aiq-runtime-site-packages` marker so package apply
can reuse the extracted runtime.

### `package`

For a generated scenario:

1. Create or reuse the scenario's local venv.
2. Install from its `.pipdownload` wheelhouse and `requirements.txt` with `--no-index`.
3. If the generated scenario was created from an image-backed runtime, link the extracted runtime
   site-packages into the venv with a `.pth` file and prepend extracted console scripts such as
   `fullrelease` to `PATH`.
4. Generate `descriptor-processed.json` through the Scenario Wizard packaging module.
5. Copy venv-installed scenario dependencies into `bin/`.
6. Compress the scenario with the Scenario Wizard compression class.
7. Emit the target zip path.

This mirrors the generated Makefile's local packaging path while removing Docker and implicit PyPI
fallbacks. The CLI uses the image's packaging modules where they are deterministic and local, but
it does not run the network-capable `p` stage from `package pdc`.

Current status: dry-run planning, fixture-backed apply execution, and real image-backed package
execution are implemented. The command validates generated scenario inputs including requirements,
wheelhouse, descriptor, setup config, and main entrypoint files, refuses ambiguous existing package
zips unless `--force` is explicit, creates or reuses `venv`, installs with `--no-index`, links the
image runtime through a `.pth` file when present, stages venv-installed dependencies into `bin/`,
compresses locally, and emits generated zip paths, sizes, and checksums.

## Why Not Copy The Container Venv Directly?

Copying a venv out of a container is fragile:

- paths often point at `/usr/src/folder`
- symlinks point at container Python paths
- package entrypoints may need rewriting
- platform tags can be wrong for Windows or WSL
- provenance is weak unless checksums are captured

The generated Makefiles already work around some of this by rewriting paths and relinking Python.
For a mature CLI workflow, prefer creating a local venv from a versioned wheelhouse and manifest.

## Failure Modes

| Failure | Behavior |
| --- | --- |
| Python 3.12 missing | Fail with install/select guidance. |
| Runtime bundle absent | Fail closed and point to `runtime prepare`. |
| Bundle version mismatch | Fail unless `--allow-version-mismatch` is explicitly provided. |
| Missing wheel | Fail with package name and expected wheelhouse path. |
| Secret-like file detected | Warn and exclude from manifest/output. |
| Generated scenario already exists | Require `--force` or a new output path. |

## Maturity Requirements

Implemented:

- Add fixture-driven tests for `runtime inspect`.
- Add redaction tests for `pip.conf`, tokens, passwords, and Docker auth strings.
- Add runtime bundle validation tests.
- Add dry-run/apply-gated `--from-bundle` runtime preparation tests.
- Add dry-run/apply-gated `--from-image-tar` runtime preparation tests for filesystem and
  Docker-save-style tars.
- Add no-network tests for venv command planning.
- Add fixture-backed `create --apply` tests with redacted subprocess output.
- Add fixture-backed `package --apply` tests with redacted subprocess output.
- Validate trusted image-tar prepare, real create apply, and real package apply with the
  generated seed scenario.

Before broad operator package upload usage:

- Repeat validation for each custom scenario shape that will be uploaded.
- Add docs screenshots only with synthetic scenario names.
- Keep all generated packages and runtime caches out of git.

## Implementation Order

1. Done: add `scenario-wizard runtime inspect` for zip metadata and bundle detection.
2. Done: add runtime bundle manifest model and validation.
3. Done: add `create --dry-run` that emits the exact local steps without running them.
4. Done: add `runtime prepare --from-bundle` with dry-run/apply gating.
5. Done: add local `create --apply` against a synthetic fixture bundle.
6. Done: add package planning and local package execution against a synthetic fixture.
7. Done: add `runtime prepare --from-image-tar` for trusted filesystem and Docker-save tars.
8. Done: validate create/package against a trusted Scenario Wizard image-tar-derived runtime bundle
   and real wheelhouse.
9. Done: repeat package validation across the remaining custom scenario templates and wire the flow
   into custom scenario upload.
10. Done: remove the remaining create-time shell-wrapper/runtime-workspace dependency and execute
    create through direct Python imports from the bundle `runtime/` and `python/` directories.

## Security Notes

- Never read or print Docker Hub credentials from the PDF.
- Never commit `pip.conf` if it contains credentialed indexes.
- Keep runtime cache under the user's cache directory, not under the repo.
- Redact any URL containing credentials before writing logs or manifests.
