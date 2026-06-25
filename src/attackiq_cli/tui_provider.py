from __future__ import annotations

import contextlib
import copy
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

from attackiq_cli.config import (
    ENV_ACCOUNT_TOKEN,
    ENV_BASE_URL,
    ENV_JWT,
    config_dir,
)
from attackiq_cli.services import (
    ResultsMode,
    ScenarioFilters,
    ServiceContext,
    fetch_assessment_detail,
    fetch_assessments_page,
    fetch_asset_detail,
    fetch_assets_page,
    fetch_phase_logs,
    fetch_phase_results,
    fetch_results_list,
    fetch_scenario_detail,
    fetch_scenarios_page,
    fetch_template_detail,
    fetch_templates_page,
    fetch_test_detail,
    fetch_tests_page,
)
from attackiq_cli.spec import ENV_SPEC_CACHE_DIR, ENV_SPEC_CACHE_DISABLED, SPEC_CACHE_DIRNAME

ENV_TUI_CACHE_MAX = "ATTACKIQ_TUI_CACHE_MAX"
ENV_TUI_CACHE_TTL = "ATTACKIQ_TUI_CACHE_TTL"
DEFAULT_TUI_CACHE_MAX = 128
_CloneT = TypeVar("_CloneT")
_CacheKeyT = TypeVar("_CacheKeyT")
_CacheValueT = TypeVar("_CacheValueT")

_CACHE_DOMAINS = (
    "scenarios",
    "results",
    "assessments",
    "tests",
    "assets",
    "templates",
)


@dataclass
class TuiOptions:
    page_size: int
    order_by: str | None
    search: str | None
    tag: str | None
    filter_debounce: float
    insecure: bool
    insecure_source: str
    timeout: float | None
    timeout_source: str


@dataclass
class TuiState:
    authenticated: bool
    base_url: str
    base_url_source: str
    auth_mode: str
    auth_source: str
    spec_cache_status: str
    spec_cache_dir: str
    spec_cache_dir_source: str
    spec_load_source: str
    env_display: str
    workspace_display: str
    workspace_full: str


class ResultsViewMode(Enum):
    SUMMARIES = "Summaries"
    PHASES = "Phases"
    LOGS = "Logs"


class TuiDataProvider:
    def __init__(self, context: ServiceContext, options: TuiOptions) -> None:
        self.context = context
        self.options = options
        self._cache_max_entries = _resolve_tui_cache_max_entries()
        self._cache_ttl_seconds = _resolve_tui_cache_ttl_seconds()
        self._results_list_cache: dict[
            tuple[ResultsMode, int, int, str | None],
            tuple[float, tuple[list[dict[str, Any]], bool]],
        ] = {}
        self._phase_results_cache: dict[
            tuple[str | None, str | None, int, int],
            tuple[float, list[dict[str, Any]]],
        ] = {}
        self._phase_logs_cache: dict[
            tuple[str | None, str | None, int, int],
            tuple[float, list[dict[str, Any]]],
        ] = {}
        self._scenarios_page_cache: dict[
            tuple[int, int, ScenarioFilters],
            tuple[float, tuple[list[dict[str, Any]], bool]],
        ] = {}
        self._scenario_detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._assessments_page_cache: dict[
            tuple[int, int, tuple[tuple[str, Any], ...]],
            tuple[float, tuple[list[dict[str, Any]], bool]],
        ] = {}
        self._assessment_detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._tests_page_cache: dict[
            tuple[int, int, tuple[tuple[str, Any], ...]],
            tuple[float, tuple[list[dict[str, Any]], bool]],
        ] = {}
        self._test_detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._assets_page_cache: dict[
            tuple[int, int, tuple[tuple[str, Any], ...]],
            tuple[float, tuple[list[dict[str, Any]], bool]],
        ] = {}
        self._asset_detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._templates_page_cache: dict[
            tuple[int, int, tuple[tuple[str, Any], ...]],
            tuple[float, tuple[list[dict[str, Any]], bool]],
        ] = {}
        self._template_detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def _invalidate_expired_caches(self) -> None:
        _cache_prune_expired(self._results_list_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._phase_results_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._phase_logs_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._scenarios_page_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._scenario_detail_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._assessments_page_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._assessment_detail_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._tests_page_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._test_detail_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._assets_page_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._asset_detail_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._templates_page_cache, ttl_seconds=self._cache_ttl_seconds)
        _cache_prune_expired(self._template_detail_cache, ttl_seconds=self._cache_ttl_seconds)

    def build_state(self) -> TuiState:
        authenticated = bool(self.context.auth.account_token or self.context.auth.jwt)
        workspace_full = self._resolve_workspace()
        base_url_source = _resolve_base_url_source(self.context.config)
        auth_mode = _resolve_auth_mode(self.context.auth)
        auth_source = _resolve_auth_source(self.context.config, auth_mode)
        spec_cache_status = "disabled" if _is_spec_cache_disabled() else "enabled"
        spec_cache_dir = _resolve_spec_cache_dir()
        spec_cache_dir_source = "env" if _has_env_value(ENV_SPEC_CACHE_DIR) else "default"
        spec_load_source = _resolve_spec_load_source(self.context.spec)
        return TuiState(
            authenticated=authenticated,
            base_url=self.context.base_url,
            base_url_source=base_url_source,
            auth_mode=auth_mode,
            auth_source=auth_source,
            spec_cache_status=spec_cache_status,
            spec_cache_dir=spec_cache_dir,
            spec_cache_dir_source=spec_cache_dir_source,
            spec_load_source=spec_load_source,
            env_display=_format_env_display(self.context.base_url),
            workspace_display=_shorten_path(workspace_full),
            workspace_full=workspace_full,
        )

    def _resolve_workspace(self) -> str:
        configured = getattr(self.context.config, "workspace_dir", None)
        if isinstance(configured, str) and configured.strip():
            return str(Path(configured).expanduser())
        repo_root = _find_repo_root(Path.cwd())
        if repo_root is not None:
            return str(repo_root)
        return str(Path.cwd())

    def _to_results_mode(self, mode: ResultsViewMode) -> ResultsMode:
        if mode == ResultsViewMode.SUMMARIES:
            return ResultsMode.SUMMARIES
        if mode == ResultsViewMode.PHASES:
            return ResultsMode.PHASES
        return ResultsMode.LOGS

    def fetch_results_list(
        self,
        *,
        mode: ResultsViewMode,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        mode_key = self._to_results_mode(mode)
        cache_key = (mode_key, page, page_size, search)
        if cache_key in self._results_list_cache:
            cached = _cache_get(
                self._results_list_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                items, has_next = cached
                return _clone_json_data(items), has_next
        items, has_next = fetch_results_list(
            self.context,
            mode=mode_key,
            page=page,
            page_size=page_size,
            search=search,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._results_list_cache,
            cache_key,
            (_clone_json_data(items), has_next),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(items), has_next

    def fetch_phase_results(
        self,
        *,
        result_summary_id: str | None = None,
        scenario_job_id: str | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        resolved_page_size = page_size or self.options.page_size
        cache_key = (result_summary_id, scenario_job_id, page, resolved_page_size)
        if cache_key in self._phase_results_cache:
            cached = _cache_get(
                self._phase_results_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        records = fetch_phase_results(
            self.context,
            result_summary_id=result_summary_id,
            scenario_job_id=scenario_job_id,
            page=page,
            page_size=resolved_page_size,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._phase_results_cache,
            cache_key,
            _clone_json_data(records),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(records)

    def fetch_phase_logs(
        self,
        *,
        result_summary_id: str | None = None,
        scenario_job_id: str | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        resolved_page_size = page_size or self.options.page_size
        cache_key = (result_summary_id, scenario_job_id, page, resolved_page_size)
        if cache_key in self._phase_logs_cache:
            cached = _cache_get(
                self._phase_logs_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        records = fetch_phase_logs(
            self.context,
            result_summary_id=result_summary_id,
            scenario_job_id=scenario_job_id,
            page=page,
            page_size=resolved_page_size,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._phase_logs_cache,
            cache_key,
            _clone_json_data(records),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(records)

    def fetch_scenarios_page(
        self,
        *,
        page: int,
        page_size: int,
        filters: ScenarioFilters,
    ) -> tuple[list[dict[str, Any]], bool]:
        cache_key = (page, page_size, filters)
        if cache_key in self._scenarios_page_cache:
            cached = _cache_get(
                self._scenarios_page_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                items, has_next = cached
                return _clone_json_data(items), has_next
        items, has_next = fetch_scenarios_page(
            self.context,
            page=page,
            page_size=page_size,
            filters=filters,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        cloned_items = _clone_json_data(items)
        _cache_set(
            self._scenarios_page_cache,
            cache_key,
            (_clone_json_data(cloned_items), has_next),
            max_entries=self._cache_max_entries,
        )
        return cloned_items, has_next

    def fetch_scenario_detail(self, *, scenario_id: str) -> dict[str, Any]:
        if scenario_id in self._scenario_detail_cache:
            cached = _cache_get(
                self._scenario_detail_cache,
                scenario_id,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        detail = fetch_scenario_detail(
            self.context,
            scenario_id=scenario_id,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        detail_clone = _clone_json_data(detail)
        _cache_set(
            self._scenario_detail_cache,
            scenario_id,
            _clone_json_data(detail_clone),
            max_entries=self._cache_max_entries,
        )
        return detail_clone

    def clear_scenarios_cache(self) -> None:
        self._scenarios_page_cache.clear()
        self._scenario_detail_cache.clear()

    def clear_results_cache(self) -> None:
        self._results_list_cache.clear()
        self._phase_results_cache.clear()
        self._phase_logs_cache.clear()

    def fetch_assessments_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        resolved_query = dict(query_params) if query_params else {}
        frozen_query = _freeze_query_params(query_params)
        cache_key = (page, page_size, frozen_query)
        if cache_key in self._assessments_page_cache:
            cached = _cache_get(
                self._assessments_page_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                items, has_next = cached
                return _clone_json_data(items), has_next
        items, has_next = fetch_assessments_page(
            self.context,
            page=page,
            page_size=page_size,
            query_params=resolved_query or None,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._assessments_page_cache,
            cache_key,
            (_clone_json_data(items), has_next),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(items), has_next

    def fetch_assessment_detail(self, *, assessment_id: str) -> dict[str, Any]:
        if assessment_id in self._assessment_detail_cache:
            cached = _cache_get(
                self._assessment_detail_cache,
                assessment_id,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        detail = fetch_assessment_detail(
            self.context,
            assessment_id=assessment_id,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        detail_clone = _clone_json_data(detail)
        _cache_set(
            self._assessment_detail_cache,
            assessment_id,
            _clone_json_data(detail_clone),
            max_entries=self._cache_max_entries,
        )
        return detail_clone

    def fetch_tests_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        resolved_query = dict(query_params) if query_params else {}
        frozen_query = _freeze_query_params(query_params)
        cache_key = (page, page_size, frozen_query)
        if cache_key in self._tests_page_cache:
            cached = _cache_get(
                self._tests_page_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                items, has_next = cached
                return _clone_json_data(items), has_next
        items, has_next = fetch_tests_page(
            self.context,
            page=page,
            page_size=page_size,
            query_params=resolved_query or None,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._tests_page_cache,
            cache_key,
            (_clone_json_data(items), has_next),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(items), has_next

    def fetch_test_detail(self, *, test_id: str) -> dict[str, Any]:
        if test_id in self._test_detail_cache:
            cached = _cache_get(
                self._test_detail_cache,
                test_id,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        detail = fetch_test_detail(
            self.context,
            test_id=test_id,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        detail_clone = _clone_json_data(detail)
        _cache_set(
            self._test_detail_cache,
            test_id,
            _clone_json_data(detail_clone),
            max_entries=self._cache_max_entries,
        )
        return detail_clone

    def fetch_assets_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        resolved_query = dict(query_params) if query_params else {}
        frozen_query = _freeze_query_params(query_params)
        cache_key = (page, page_size, frozen_query)
        if cache_key in self._assets_page_cache:
            cached = _cache_get(
                self._assets_page_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                items, has_next = cached
                return _clone_json_data(items), has_next
        items, has_next = fetch_assets_page(
            self.context,
            page=page,
            page_size=page_size,
            query_params=resolved_query or None,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._assets_page_cache,
            cache_key,
            (_clone_json_data(items), has_next),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(items), has_next

    def fetch_asset_detail(self, *, asset_id: str) -> dict[str, Any]:
        if asset_id in self._asset_detail_cache:
            cached = _cache_get(
                self._asset_detail_cache,
                asset_id,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        detail = fetch_asset_detail(
            self.context,
            asset_id=asset_id,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        detail_clone = _clone_json_data(detail)
        _cache_set(
            self._asset_detail_cache,
            asset_id,
            _clone_json_data(detail_clone),
            max_entries=self._cache_max_entries,
        )
        return detail_clone

    def fetch_templates_page(
        self,
        *,
        page: int,
        page_size: int,
        query_params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        resolved_query = dict(query_params) if query_params else {}
        frozen_query = _freeze_query_params(query_params)
        cache_key = (page, page_size, frozen_query)
        if cache_key in self._templates_page_cache:
            cached = _cache_get(
                self._templates_page_cache,
                cache_key,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                items, has_next = cached
                return _clone_json_data(items), has_next
        items, has_next = fetch_templates_page(
            self.context,
            page=page,
            page_size=page_size,
            query_params=resolved_query or None,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        _cache_set(
            self._templates_page_cache,
            cache_key,
            (_clone_json_data(items), has_next),
            max_entries=self._cache_max_entries,
        )
        return _clone_json_data(items), has_next

    def fetch_template_detail(self, *, template_id: str) -> dict[str, Any]:
        if template_id in self._template_detail_cache:
            cached = _cache_get(
                self._template_detail_cache,
                template_id,
                ttl_seconds=self._cache_ttl_seconds,
            )
            if cached is not None:
                return _clone_json_data(cached)
        detail = fetch_template_detail(
            self.context,
            template_id=template_id,
            insecure=self.options.insecure,
            timeout=self.options.timeout,
        )
        detail_clone = _clone_json_data(detail)
        _cache_set(
            self._template_detail_cache,
            template_id,
            _clone_json_data(detail_clone),
            max_entries=self._cache_max_entries,
        )
        return detail_clone

    def clear_assessments_cache(self) -> None:
        self._assessments_page_cache.clear()
        self._assessment_detail_cache.clear()

    def clear_tests_cache(self) -> None:
        self._tests_page_cache.clear()
        self._test_detail_cache.clear()

    def clear_assets_cache(self) -> None:
        self._assets_page_cache.clear()
        self._asset_detail_cache.clear()

    def clear_templates_cache(self) -> None:
        self._templates_page_cache.clear()
        self._template_detail_cache.clear()

    def scenarios_cache_stats(self) -> tuple[int, int]:
        self._invalidate_expired_caches()
        return len(self._scenarios_page_cache), len(self._scenario_detail_cache)

    def results_cache_stats(self) -> tuple[int, int, int]:
        self._invalidate_expired_caches()
        return (
            len(self._results_list_cache),
            len(self._phase_results_cache),
            len(self._phase_logs_cache),
        )

    def assessments_cache_stats(self) -> tuple[int, int]:
        self._invalidate_expired_caches()
        return len(self._assessments_page_cache), len(self._assessment_detail_cache)

    def tests_cache_stats(self) -> tuple[int, int]:
        self._invalidate_expired_caches()
        return len(self._tests_page_cache), len(self._test_detail_cache)

    def assets_cache_stats(self) -> tuple[int, int]:
        self._invalidate_expired_caches()
        return len(self._assets_page_cache), len(self._asset_detail_cache)

    def templates_cache_stats(self) -> tuple[int, int]:
        self._invalidate_expired_caches()
        return len(self._templates_page_cache), len(self._template_detail_cache)

    def cache_max_entries(self) -> int:
        return self._cache_max_entries

    def cache_ttl_seconds(self) -> float | None:
        return self._cache_ttl_seconds


def _find_repo_root(start: Path) -> Path | None:
    current = start
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _shorten_path(value: str) -> str:
    path = Path(value)
    if not path.parts:
        return value
    return path.name or value


def _clone_json_data(value: _CloneT) -> _CloneT:
    return copy.deepcopy(value)


def _format_env_display(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc or base_url
    label = _infer_env_label(host)
    return f"{host} ({label})"


def _infer_env_label(host: str) -> str:
    lowered = host.lower()
    if "staging" in lowered:
        return "staging"
    if "dev" in lowered:
        return "dev"
    if "prod" in lowered or "production" in lowered:
        return "prod"
    return "custom"


def _has_env_value(name: str) -> bool:
    value = os.getenv(name)
    return isinstance(value, str) and bool(value.strip())


def _cache_domain_totals(provider: TuiDataProvider) -> dict[str, int]:
    scenarios_pages, scenarios_details = provider.scenarios_cache_stats()
    results_list, results_phases, results_logs = provider.results_cache_stats()
    assessments_pages, assessments_details = provider.assessments_cache_stats()
    tests_pages, tests_details = provider.tests_cache_stats()
    assets_pages, assets_details = provider.assets_cache_stats()
    templates_pages, templates_details = provider.templates_cache_stats()
    return {
        "scenarios": scenarios_pages + scenarios_details,
        "results": results_list + results_phases + results_logs,
        "assessments": assessments_pages + assessments_details,
        "tests": tests_pages + tests_details,
        "assets": assets_pages + assets_details,
        "templates": templates_pages + templates_details,
    }


def _format_cache_totals_compact(cache_totals: dict[str, int]) -> str:
    return ", ".join(f"{domain}={cache_totals[domain]}" for domain in _CACHE_DOMAINS)


def _format_cache_entries_runtime(cache_totals: dict[str, int]) -> str:
    return "cache_entries=" + ",".join(
        f"{domain}:{cache_totals[domain]}" for domain in _CACHE_DOMAINS
    )


def _is_spec_cache_disabled() -> bool:
    raw = os.getenv(ENV_SPEC_CACHE_DISABLED, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_tui_cache_max_entries() -> int:
    raw = os.getenv(ENV_TUI_CACHE_MAX, "").strip()
    if not raw:
        return DEFAULT_TUI_CACHE_MAX
    with contextlib.suppress(ValueError):
        value = int(raw)
        if value >= 1:
            return value
    return DEFAULT_TUI_CACHE_MAX


def _resolve_tui_cache_ttl_seconds() -> float | None:
    raw = os.getenv(ENV_TUI_CACHE_TTL, "").strip()
    if not raw:
        return None
    with contextlib.suppress(ValueError):
        value = float(raw)
        if value > 0:
            return value
    return None


def _resolve_spec_cache_dir() -> str:
    override = os.getenv(ENV_SPEC_CACHE_DIR)
    if isinstance(override, str) and override.strip():
        return str(Path(override).expanduser())
    return str(config_dir() / SPEC_CACHE_DIRNAME)


def _freeze_query_params(params: dict[str, Any] | None) -> tuple[tuple[str, Any], ...]:
    if not params:
        return ()
    return tuple(sorted((str(key), _freeze_value(value)) for key, value in params.items()))


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze_value(entry)) for key, entry in value.items()))
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(entry) for entry in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(entry) for entry in value))
    return value


def _cache_get(
    cache: dict[_CacheKeyT, tuple[float, _CacheValueT]],
    key: _CacheKeyT,
    *,
    ttl_seconds: float | None,
) -> _CacheValueT | None:
    created, value = cache.pop(key)
    if ttl_seconds is not None and (time.monotonic() - created) >= ttl_seconds:
        return None
    cache[key] = (created, value)
    return value


def _cache_set(
    cache: dict[_CacheKeyT, tuple[float, _CacheValueT]],
    key: _CacheKeyT,
    value: _CacheValueT,
    *,
    max_entries: int,
) -> None:
    if key in cache:
        cache.pop(key)
    cache[key] = (time.monotonic(), value)
    while len(cache) > max_entries:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)


def _cache_prune_expired(
    cache: dict[_CacheKeyT, tuple[float, _CacheValueT]],
    *,
    ttl_seconds: float | None,
) -> None:
    if ttl_seconds is None:
        return
    now = time.monotonic()
    expired_keys = [
        key for key, (created, _value) in cache.items() if (now - created) >= ttl_seconds
    ]
    for key in expired_keys:
        cache.pop(key, None)


def _resolve_spec_load_source(spec: Any) -> str:
    source = getattr(spec, "load_source", None)
    if isinstance(source, str) and source.strip():
        return source
    return "unknown"


def _resolve_base_url_source(config: Any) -> str:
    if _has_env_value(ENV_BASE_URL):
        return "env"
    configured = getattr(config, "base_url", None)
    if isinstance(configured, str) and configured.strip():
        return "config"
    return "unset"


def _resolve_auth_mode(auth: Any) -> str:
    preferred = getattr(auth, "preferred_scheme", "auto")
    if preferred in {"account-token", "jwt", "none"}:
        return preferred
    if getattr(auth, "account_token", None):
        return "account-token"
    if getattr(auth, "jwt", None):
        return "jwt"
    return "none"


def _resolve_auth_source(config: Any, auth_mode: str) -> str:
    if auth_mode == "account-token":
        if _has_env_value(ENV_ACCOUNT_TOKEN):
            return "env"
        configured = getattr(config, "account_token", None)
        if isinstance(configured, str) and configured.strip():
            return "config"
    if auth_mode == "jwt":
        if _has_env_value(ENV_JWT):
            return "env"
        configured = getattr(config, "jwt", None)
        if isinstance(configured, str) and configured.strip():
            return "config"
    return "unset"
