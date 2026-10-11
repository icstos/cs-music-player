"""跨线程回调调度：把桌面歌词窗口线程里的回调投递回 Flet 事件循环。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

__all__ = ["FletLoopDispatcher"]


class FletLoopDispatcher:
    """``Dispatcher`` 的 Flet 实现。

    ``page.run_task`` 内部用 ``asyncio.run_coroutine_threadsafe``，可以从任意
    线程安全调用；这里把同步回调包成协程再排队，于是服务层收到的回调永远
    跑在 UI 事件循环上——视图模型因此可以假定自己是单线程的。
    """

    def __init__(self, page: ft.Page) -> None:
        self._page = page

    def __call__(self, callback: Callable[[], None]) -> None:
        """把 ``callback`` 排到 UI 事件循环执行。"""

        async def runner() -> None:
            callback()

        self._page.run_task(runner)
