"""睡眠定时器：倒计时回调与格式化。"""

from __future__ import annotations

import asyncio

from cs_music_player.service.sleep import SleepTimerService, run_sleep_countdown
from cs_music_player.view.components.format import fmt_duration


def test_fmt_duration_minutes_and_seconds() -> None:
    assert fmt_duration(0) == "00:00"
    assert fmt_duration(59) == "00:59"
    assert fmt_duration(60) == "01:00"
    assert fmt_duration(754) == "12:34"


def test_fmt_duration_includes_hours() -> None:
    assert fmt_duration(3600) == "1:00:00"
    assert fmt_duration(3725) == "1:02:05"


def test_fmt_duration_clamps_negative() -> None:
    assert fmt_duration(-5) == "00:00"
    assert fmt_duration(30.9) == "00:30"


def test_sleep_countdown_ticks_and_completes() -> None:
    ticks: list[float] = []

    async def run() -> None:
        await run_sleep_countdown(2, ticks.append)

    asyncio.run(run())
    # 每秒回调一次，剩余时间单调递减且为正
    assert len(ticks) >= 2
    assert ticks[0] > ticks[-1] > 0


def test_sleep_service_fires_elapsed_once() -> None:
    ticks: list[float] = []
    elapsed: list[bool] = []

    async def run() -> None:
        service = SleepTimerService(ticks.append, lambda: elapsed.append(True))
        service.start(2)
        assert service.active
        await asyncio.sleep(3.2)
        assert not service.active
        assert service.remaining == 0.0

    asyncio.run(run())
    assert len(ticks) >= 2
    assert elapsed == [True]


def test_sleep_service_cancel_resets_state() -> None:
    ticks: list[float] = []
    elapsed: list[bool] = []

    async def run() -> None:
        service = SleepTimerService(ticks.append, lambda: elapsed.append(True))
        service.start(100)
        service.cancel()
        await asyncio.sleep(0.05)
        assert not service.active
        assert service.remaining == 0.0

    asyncio.run(run())
    assert elapsed == []
