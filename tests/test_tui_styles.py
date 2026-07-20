from __future__ import annotations

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_styles


def test_tui_stylesheet_contains_core_selectors() -> None:
    assert "Screen {" in tui_styles.TUI_CSS
    assert "#header_bar" in tui_styles.TUI_CSS
    assert "#command_palette_overlay" in tui_styles.TUI_CSS
    assert ".request-preview-dialog" in tui_styles.TUI_CSS
    assert "AssessmentDefaultsPreviewScreen" in tui_styles.TUI_CSS
    assert "NewAssessmentPreviewScreen" in tui_styles.TUI_CSS
    assert "AssessmentFromTemplatePreviewScreen" in tui_styles.TUI_CSS
    assert "NewTestPreviewScreen" in tui_styles.TUI_CSS
    assert "TestScenariosPreviewScreen" in tui_styles.TUI_CSS
    assert "TestStatusPreviewScreen" in tui_styles.TUI_CSS
    assert "#results_list_status" in tui_styles.TUI_CSS


def test_attackiq_tui_app_uses_shared_stylesheet() -> None:
    assert tui_module.AttackIQTuiApp.CSS is tui_styles.TUI_CSS
