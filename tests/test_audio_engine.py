"""音频引擎：挂载点、状态跨重建、事件转发。

这些都是「单元级」契约：不碰音频设备、不建窗口，只验证引擎对
``flet_audio`` 控件生命周期的管理是否正确 —— 因为真正跑起来时，这里错了
只会表现为「切歌没声音」，最难从现象反推原因。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft
import flet_audio as fa
import pytest

from cs_music_player.infra.audio import FletAudioEngine


class FakeHost:
    """最小页面契约：``services`` + ``update()``。"""

    def __init__(self) -> None:
        self.services: list[Any] = []
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


class FakeAudio:
    """记录构造参数与属性写入的假控件。"""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.src = kwargs.get("src")
        self.volume = kwargs.get("volume")
        self.playback_rate = kwargs.get("playback_rate")
        self.updates = 0
        self.commands: list[str] = []
        self.seeked_to: list[float] = []

    def update(self) -> None:
        self.updates += 1

    async def pause(self) -> None:
        self.commands.append("pause")

    async def resume(self) -> None:
        self.commands.append("resume")

    async def seek(self, position: Any) -> None:
        self.seeked_to.append(float(position.in_milliseconds) / 1000.0)


class FakeObserver:
    """记录引擎上报的全部事件。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    def on_position(self, seconds: float) -> None:
        self.events.append(("position", seconds))

    def on_duration(self, seconds: float) -> None:
        self.events.append(("duration", seconds))

    def on_play_state(self, playing: bool) -> None:
        self.events.append(("playing", playing))

    def on_completed(self) -> None:
        self.events.append(("completed", None))


@pytest.fixture
def rig() -> tuple[FletAudioEngine, FakeHost, FakeObserver]:
    host = FakeHost()
    observer = FakeObserver()
    engine = FletAudioEngine(
        host, observer, volume=0.7, speed=1.0, audio_factory=FakeAudio
    )
    return engine, host, observer


def _state_event(state: fa.AudioState) -> Any:
    return type("Event", (), {"state": state})()


def _position_event(milliseconds: int) -> Any:
    return type("Event", (), {"position": milliseconds})()


def _duration_event(seconds: float) -> Any:
    return type("Event", (), {"duration": ft.Duration(seconds=seconds)})()


# ── 挂载 / 卸载 ── #


def test_load_mounts_a_control_with_current_volume_and_speed(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, _ = rig
    engine.set_volume(0.4)
    engine.set_speed(1.5)

    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))

    assert len(host.services) == 1
    audio = host.services[0]
    assert audio.src == "a.mp3"
    assert audio.kwargs["autoplay"] is True
    # 引擎属性必须带到新控件上，否则「调过音量后切歌会变回默认」
    assert audio.volume == pytest.approx(0.4)
    assert audio.playback_rate == pytest.approx(1.5)
    assert host.updates == 1


def test_second_load_replaces_the_previous_control(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, _ = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    first = host.services[0]
    asyncio.run(engine.load(Path("b.mp3"), autoplay=False))

    assert len(host.services) == 1, "旧控件必须被摘掉，否则两首歌会同时响"
    assert host.services[0] is not first
    assert host.services[0].kwargs["autoplay"] is False


def test_dispose_detaches_and_is_idempotent(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, _ = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    engine.dispose()
    engine.dispose()

    assert host.services == []
    assert engine.playing is False


# ── 属性 ── #


@pytest.mark.parametrize(
    "value, expected", [(0.4, 0.4), (-1, 0.0), (2, 1.0), (float("nan"), 0.0)]
)
def test_volume_is_clamped(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver], value: float, expected: float
) -> None:
    engine, _, _ = rig
    engine.set_volume(value)
    assert engine.volume == pytest.approx(expected)


def test_volume_and_speed_reach_the_live_control(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, _ = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    audio = host.services[0]

    engine.set_volume(0.25)
    engine.set_speed(2.0)

    assert audio.volume == pytest.approx(0.25)
    assert audio.playback_rate == pytest.approx(2.0)
    # 属性写入后必须下发补丁，否则客户端还是旧音量
    assert audio.updates == 2


def test_pause_and_resume_are_forwarded(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, _ = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    audio = host.services[0]

    asyncio.run(engine.set_paused(True))
    asyncio.run(engine.set_paused(False))

    assert audio.commands == ["pause", "resume"]


def test_seek_before_any_track_is_a_no_op(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, _ = rig
    import asyncio

    asyncio.run(engine.seek(12.0))  # 不抛异常即可


def test_seek_is_converted_to_a_duration(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, _ = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    asyncio.run(engine.seek(12.5))

    assert host.services[0].seeked_to == [pytest.approx(12.5)]


# ── 事件 ── #


def test_state_events_drive_the_playing_flag(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, observer = rig

    engine._on_state(_state_event(fa.AudioState.PLAYING))
    assert engine.playing is True
    engine._on_state(_state_event(fa.AudioState.PAUSED))
    assert engine.playing is False

    assert observer.events == [("playing", True), ("playing", False)]


def test_completed_reports_stop_and_completion(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, observer = rig

    engine._on_state(_state_event(fa.AudioState.COMPLETED))

    assert engine.playing is False
    # 引擎本来就没在播，标志无变化 ⇒ 只报「播完了」，不重复刷一条暂停
    assert observer.events == [("completed", None)]


def test_completed_while_playing_reports_both(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, host, observer = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))  # autoplay ⇒ 引擎认为在播
    engine._on_state(_state_event(fa.AudioState.COMPLETED))

    assert observer.events == [("playing", True), ("playing", False), ("completed", None)]


# ── 播放状态不依赖控件事件 ── #


def test_load_with_autoplay_reports_playing_without_any_event(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    """Windows 上 ``PLAYING`` 事件可能早于挂载就发完，界面不能因此停在暂停。"""
    engine, _, observer = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3"), autoplay=True))

    assert engine.playing is True
    assert observer.events == [("playing", True)]


def test_load_without_autoplay_stays_paused(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, observer = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3"), autoplay=False))

    assert engine.playing is False
    assert observer.events == []


def test_switching_track_while_playing_keeps_the_flag_quiet(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    """连播切歌：本来就是播放中，不该再报一次「开始播放」。"""
    engine, _, observer = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    asyncio.run(engine.load(Path("b.mp3")))

    assert engine.playing is True
    assert observer.events == [("playing", True)]


def test_pause_and_resume_update_the_flag(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, observer = rig
    import asyncio

    asyncio.run(engine.load(Path("a.mp3")))
    asyncio.run(engine.set_paused(True))
    asyncio.run(engine.set_paused(False))

    assert engine.playing is True
    assert observer.events == [
        ("playing", True),
        ("playing", False),
        ("playing", True),
    ]


def test_duplicate_state_event_does_not_report_twice(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, observer = rig

    engine._on_state(_state_event(fa.AudioState.PLAYING))
    engine._on_state(_state_event(fa.AudioState.PLAYING))

    assert observer.events == [("playing", True)]


def test_position_is_reported_in_seconds(
    rig: tuple[FletAudioEngine, FakeHost, FakeObserver],
) -> None:
    engine, _, observer = rig

    engine._on_position(_position_event(1500))
    engine._on_duration(_duration_event(184.0))

    assert observer.events == [("position", 1.5), ("duration", 184.0)]
