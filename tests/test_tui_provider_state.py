from attackiq_cli import tui_provider, tui_provider_state


def test_tui_provider_reexports_runtime_state_symbols() -> None:
    assert tui_provider.TuiState is tui_provider_state.TuiState
    assert tui_provider._format_env_display is tui_provider_state._format_env_display
    assert tui_provider._has_env_value is tui_provider_state._has_env_value
    assert tui_provider._infer_env_label is tui_provider_state._infer_env_label
    assert tui_provider._is_spec_cache_disabled is tui_provider_state._is_spec_cache_disabled
    assert tui_provider._resolve_auth_mode is tui_provider_state._resolve_auth_mode
    assert tui_provider._resolve_auth_source is tui_provider_state._resolve_auth_source
    assert tui_provider._resolve_base_url_source is tui_provider_state._resolve_base_url_source
    assert tui_provider._resolve_spec_cache_dir is tui_provider_state._resolve_spec_cache_dir
    assert tui_provider._resolve_spec_load_source is tui_provider_state._resolve_spec_load_source
    assert tui_provider._shorten_path is tui_provider_state._shorten_path
