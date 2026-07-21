from __future__ import annotations

import asyncio
import concurrent.futures
import threading

import pytest

from attackiq_cli import tui as tui_module
from attackiq_cli import tui_tasks
from attackiq_cli.tui_tasks import (
    _cancel_and_await_tasks,
    _replace_task,
    _run_blocking,
    _schedule_debounced,
)


@pytest.mark.anyio
async def test_cancel_and_await_tasks_cancels_pending_tasks() -> None:
    task = asyncio.create_task(asyncio.sleep(30))

    await _cancel_and_await_tasks(task)

    assert task.done()
    assert task.cancelled()


@pytest.mark.anyio
async def test_replace_task_cancels_existing_and_runs_replacement() -> None:
    events: list[str] = []
    existing = asyncio.create_task(asyncio.sleep(30))

    async def replacement() -> None:
        events.append("replacement")

    task = _replace_task(existing, replacement())
    await task
    await asyncio.gather(existing, return_exceptions=True)

    assert existing.cancelled()
    assert events == ["replacement"]


@pytest.mark.anyio
async def test_schedule_debounced_cancels_existing_before_action() -> None:
    events: list[str] = []

    async def action() -> None:
        events.append("ran")

    first = _schedule_debounced(None, 30, action)
    second = _schedule_debounced(first, 0, action)
    await second
    await asyncio.gather(first, return_exceptions=True)

    assert first.cancelled()
    assert events == ["ran"]


@pytest.mark.anyio
async def test_run_blocking_without_executor_calls_inline() -> None:
    seen: list[str] = []

    def build_value(value: str, *, suffix: str) -> str:
        seen.append("called")
        return f"{value}-{suffix}"

    result = await _run_blocking(None, build_value, "alpha", suffix="beta")

    assert result == "alpha-beta"
    assert seen == ["called"]


@pytest.mark.anyio
async def test_run_blocking_uses_executor_when_available() -> None:
    main_thread = threading.get_ident()

    def current_thread() -> int:
        return threading.get_ident()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        worker_thread = await _run_blocking(executor, current_thread)

    assert worker_thread != main_thread


def test_tui_module_reexports_run_blocking_for_compatibility() -> None:
    assert tui_module._run_blocking is tui_tasks._run_blocking
