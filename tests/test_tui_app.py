from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_app


def test_tui_module_reexports_app_shell_for_compatibility() -> None:
    assert tui_module.AttackIQTuiApp is tui_app.AttackIQTuiApp
