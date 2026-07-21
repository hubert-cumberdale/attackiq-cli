from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_tests


def test_tui_module_reexports_tests_tab_for_compatibility() -> None:
    assert tui_module.WorkflowTestsTab is tui_tests.WorkflowTestsTab


def test_tui_module_reexports_test_status_preview_for_compatibility() -> None:
    assert tui_module.TestStatusPreviewScreen.__module__ == "attackiq_cli.tui_preview"
    assert tui_module.build_test_status_preview.__module__ == "attackiq_cli.tui_preview"
