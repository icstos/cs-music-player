"""睡眠定时器服务：倒计时到点后通知宿主关闭软件。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

__all__ = ["SleepTimerService", "run_sleep_countdown"]


async def run_sleep_countdown(total: float, on_tick: Callable[[float], None]) -> None:
    """倒计时主循环：按**绝对截止时间**每秒回调一次剩余秒数。

    用绝对截止时间而不是「每次减一」，是为了让系统休眠 / 调度抖动不会
    累积误差。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + total
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        on_tick(max(0.0, remaining))
        await asyncio.sleep(1.0)


class SleepTimerService:
    """一次性的睡眠倒计时。

    Args:
        on_tick: 每秒回调一次剩余秒数。
        on_elapsed: 倒计时归零后回调一次（宿主负责关窗）。
    """

    def __init__(
        self,
        on_tick: Callable[[float], None],
        on_elapsed: Callable[[], None],
    ) -> None:
        self._on_tick = on_tick
        self._on_elapsed = on_elapsed
        self._task: asyncio.Task[None] | None = None
        self._remaining = 0.0

    @property
    def remaining(self) -> float:
        """剩余秒数；未启动时为 ``0.0``。"""
        return self._remaining

    @property
    def active(self) -> bool:
        """是否正在倒计时。"""
        return self._task is not None and not self._task.done()

    def start(self, total: float) -> None:
        """启动（或重置）倒计时。"""
        self.cancel()
        self._remaining = float(total)
        self._on_tick(self._remaining)
        self._task = asyncio.create_task(self._countdown(float(total)))

    def cancel(self) -> None:
        """取消倒计时（未启动时为空操作）。"""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
        self._remaining = 0.0

    async def _countdown(self, total: float) -> None:
        try:
            await run_sleep_countdown(total, self._set_remaining)
        except asyncio.CancelledError:
            raise
        self._remaining = 0.0
        self._task = None
        self._on_elapsed()

    def _set_remaining(self, value: float) -> None:
        self._remaining = value
        self._on_tick(value)
