from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PROCESS_OUTPUT_LIMIT = 4000
SUBPROCESS_ENV_ALLOWLIST = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
)

__all__ = [
    "PROCESS_OUTPUT_LIMIT",
    "SUBPROCESS_ENV_ALLOWLIST",
    "run_subprocess_action",
    "safe_process_output",
    "subprocess_env",
    "venv_bin_dir",
    "venv_subprocess_env",
]


def venv_bin_dir(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts"
    return venv_path / "bin"


def subprocess_env(
    *,
    extra_pythonpath: Path | Iterable[Path] | None = None,
    prepend_path: Path | None = None,
    home_dir: Path | None = None,
    use_setuptools_distutils: bool = False,
) -> dict[str, str]:
    env = {
        key: value
        for key in SUBPROCESS_ENV_ALLOWLIST
        if (value := os.environ.get(key))
    }
    env.setdefault("PATH", os.defpath)
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    if prepend_path is not None:
        existing_path = env.get("PATH", "")
        env["PATH"] = str(prepend_path) + os.pathsep + existing_path
    if extra_pythonpath is not None:
        env["PYTHONPATH"] = _pythonpath_value(extra_pythonpath)
    if extra_pythonpath is not None or use_setuptools_distutils:
        env["SETUPTOOLS_USE_DISTUTILS"] = "local"
    if home_dir is not None:
        home_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = home_dir / ".cache"
        tmp_dir = home_dir / "tmp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)
        env["XDG_CACHE_HOME"] = str(cache_dir)
        env["PIP_CACHE_DIR"] = str(cache_dir / "pip")
        env["TMPDIR"] = str(tmp_dir)
        env["TEMP"] = str(tmp_dir)
        env["TMP"] = str(tmp_dir)
    return env


def venv_subprocess_env(
    venv_path: Path,
    *,
    extra_pythonpath: Path | Iterable[Path] | None = None,
    prepend_path: Path | None = None,
    home_dir: Path | None = None,
    use_setuptools_distutils: bool = False,
) -> dict[str, str]:
    env = subprocess_env(
        extra_pythonpath=extra_pythonpath,
        prepend_path=prepend_path,
        home_dir=home_dir,
        use_setuptools_distutils=use_setuptools_distutils,
    )
    env["VIRTUAL_ENV"] = str(venv_path)
    existing_path = env.get("PATH", "")
    env["PATH"] = str(venv_bin_dir(venv_path)) + os.pathsep + existing_path
    return env


def run_subprocess_action(
    name: str,
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    display_argv: list[str] | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "argv": display_argv or argv,
            "cwd": str(cwd),
            "return_code": None,
            "timed_out": True,
            "stdout_tail": safe_process_output(exc.stdout or ""),
            "stderr_tail": safe_process_output(exc.stderr or ""),
        }
    except OSError as exc:
        return {
            "name": name,
            "argv": display_argv or argv,
            "cwd": str(cwd),
            "return_code": 127,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": safe_process_output(str(exc)),
        }
    return {
        "name": name,
        "argv": display_argv or argv,
        "cwd": str(cwd),
        "return_code": completed.returncode,
        "timed_out": False,
        "stdout_tail": safe_process_output(completed.stdout),
        "stderr_tail": safe_process_output(completed.stderr),
    }


def safe_process_output(value: str | bytes) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    text = re.sub(
        r"(?i)(authorization|api[_-]?key|jwt|password|secret|token)(\s*[:=]\s*)([^\r\n]+)",
        r"\1\2***",
        text,
    )
    text = re.sub(r"://([^/\s:@]+):([^/\s@]+)@", r"://***:***@", text)
    if len(text) > PROCESS_OUTPUT_LIMIT:
        return text[-PROCESS_OUTPUT_LIMIT:]
    return text


def _pythonpath_value(value: Path | Iterable[Path]) -> str:
    if isinstance(value, Path):
        return str(value)
    return os.pathsep.join(str(path) for path in value)
