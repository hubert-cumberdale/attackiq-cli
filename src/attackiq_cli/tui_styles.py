from __future__ import annotations

TUI_CSS = """
    Screen {
        layout: vertical;
    }

    #header_bar {
        layout: horizontal;
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    #header_title {
        text-style: bold;
    }

    .header-item {
        margin-right: 2;
    }

    #header_spacer {
        width: 1fr;
    }

    #banner_bar {
        height: auto;
        padding: 0 1;
        background: $error 20%;
        color: $text;
    }

    #banner_message {
        text-style: bold;
    }

    #help_overlay {
        layer: overlay;
        dock: top;
        width: 100%;
        padding: 1 2;
        background: $panel;
        border: tall $primary;
        color: $text;
    }

    #command_palette_overlay {
        layer: overlay;
        align: center middle;
        width: 80%;
        max-width: 100;
        height: 60%;
        max-height: 24;
        padding: 1;
        background: $panel;
        border: tall $accent;
    }

    #command_palette_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #command_palette_input {
        margin-bottom: 1;
    }

    #command_palette_hint {
        margin-top: 1;
        color: $text-muted;
    }

    AssessmentDefaultsPreviewScreen, AssessmentFromTemplatePreviewScreen,
    AssessmentRunPreviewScreen,
    NewAssessmentPreviewScreen, NewTestPreviewScreen,
    TestScenariosPreviewScreen, TestStatusPreviewScreen {
        align: center middle;
        background: $background 70%;
    }

    .request-preview-dialog {
        width: 90%;
        max-width: 100;
        height: 80%;
        max-height: 32;
        padding: 1 2;
        background: $panel;
        border: tall $accent;
    }

    .request-preview-actions {
        height: 3;
        margin-top: 1;
    }

    .request-preview-actions Button {
        margin-right: 1;
    }

    .request-preview-status {
        color: $success;
        text-style: bold;
        margin-top: 1;
    }

    .request-preview-error {
        color: $error;
        text-style: bold;
    }

    .request-preview-output {
        height: 1fr;
        overflow-y: auto;
        margin-top: 1;
    }

    .preview-label {
        color: $text-muted;
    }

    TabbedContent {
        height: 1fr;
    }

    .workflow-tab, .status-tab {
        padding: 0 1;
    }

    .split-pane {
        height: 1fr;
    }

    .list-pane, .detail-pane {
        border: tall $surface;
        padding: 0 1;
    }

    .list-pane {
        width: 45%;
    }

    .detail-pane {
        width: 55%;
    }

    .pane-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .pane-placeholder {
        height: 1fr;
    }

    .view-selector {
        margin-bottom: 1;
    }

    .section-title {
        text-style: bold;
        margin-top: 1;
    }

    .section-body {
        margin-bottom: 1;
    }

    #status_summary {
        margin-bottom: 1;
    }

    .status-nav {
        margin-bottom: 1;
    }

    .filter_label {
        margin-right: 1;
    }

    .filter-bar Input {
        width: 1fr;
    }

    .filter-bar Input:focus {
        border: tall $primary;
    }

    .filter-help {
        color: $text-muted;
        margin-bottom: 1;
    }

    .footer-bar {
        height: 1;
        color: $text-muted;
    }

    #results_list_status {
        margin-top: 1;
    }
    """
