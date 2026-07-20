from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_scenarios


def test_tui_module_reexports_scenarios_tab_for_compatibility() -> None:
    assert tui_module.ScenariosTab is tui_scenarios.ScenariosTab
