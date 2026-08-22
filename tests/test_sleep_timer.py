from __future__ import annotations

import asyncio

from cs_music_player.app import run_sleep_countdown
from cs_music_player.ui import fmt_duration


class _FakeWindow:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakePage:
    def __init__(self) -> None:
        self.window = _FakeWindow()
        self.tick_values: list[float] = []

    def on_tick(self, value: float) -> None:
        self.tick_values.append(value)


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
    async def run() -> None:
        page = _FakePage()
        await run_sleep_countdown(page, 2, page.on_tick)
        return page

    page = asyncio.run(run())
    # 每秒回调一次，剩余时间单调递减且为正
    assert len(page.tick_values) >= 2
    assert page.tick_values[0] > page.tick_values[-1] > 0

