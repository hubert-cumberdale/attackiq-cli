from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_assets


def test_tui_module_reexports_assets_tab_for_compatibility() -> None:
    assert tui_module.WorkflowAssetsTab is tui_assets.WorkflowAssetsTab
