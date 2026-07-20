from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import functools
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any


def _consume_task(task: asyncio.Task) -> None:
    with contextlib.suppress(asyncio.CancelledError, Exception):
        task.result()


def _cancel_task(task: asyncio.Task[Any] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()


def _replace_task(
    existing: asyncio.Task[Any] | None,
    coroutine: Coroutine[Any, Any, None],
) -> asyncio.Task[None]:
    _cancel_task(existing)
    task = asyncio.create_task(coroutine)
    task.add_done_callback(_consume_task)
    return task


async def _cancel_and_await_tasks(*tasks: asyncio.Task[Any] | None) -> None:
    active = [task for task in tasks if task is not None]
    if not active:
        return
    for task in active:
        _cancel_task(task)
    await asyncio.gather(*active, return_exceptions=True)


def _schedule_debounced(
    existing: asyncio.Task | None,
    delay: float,
    action: Callable[[], Awaitable[None]],
) -> asyncio.Task:
    if existing is not None and not existing.done():
        existing.cancel()

    async def _debounced() -> None:
        try:
            await asyncio.sleep(delay)
            await action()
        except asyncio.CancelledError:
            return

    return asyncio.create_task(_debounced())


async def _run_blocking(
    executor: concurrent.futures.Executor | None,
    func: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    if executor is None:
        return func(*args, **kwargs)
    loop = asyncio.get_running_loop()
    bound = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, bound)
