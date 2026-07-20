from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_assessments


def test_tui_module_reexports_assessments_tab_for_compatibility() -> None:
    assert tui_module.AssessmentsTab is tui_assessments.AssessmentsTab
