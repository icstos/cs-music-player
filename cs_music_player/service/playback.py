"""播放服务：曲目切换策略、播放控制与状态上报。

只依赖 ``AudioEnginePort``（音频引擎抽象）与观察者抽象；引擎由外部以
「工厂函数」注入——因为引擎反过来需要观察者（也就是本服务）才能构造。
两边都只依赖抽象，构造顺序上的循环依赖就此消解。
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from ..infra.ports import AudioEngineObserver, AudioEnginePort
from ..models import (
    MODE_ORDER,
    SPEED_MAX,
    SPEED_MIN,
    PlayMode,
    Track,
)

__all__ = [
    "EngineFactory",
    "PlaybackObserver",
    "PlaybackService",
    "next_index",
    "prev_index",
]

#: 用「观察者」造一个音频引擎。
EngineFactory = Callable[[AudioEngineObserver], AudioEnginePort]


@runtime_checkable
class PlaybackObserver(Protocol):
    """播放服务向上层播报的接口。"""

    def on_position(self, seconds: float) -> None:
        """播放进度（秒）。"""
        ...

    def on_duration(self, seconds: float) -> None:
        """曲目时长（秒）。"""
        ...

    def on_play_state(self, playing: bool) -> None:
        """播放 / 暂停状态变化。"""
        ...

    def on_track_change(self, index: int) -> None:
        """当前曲目变化。"""
        ...


# ── 纯业务规则：下一首 / 上一首是谁 ── #


def _shuffle_index(current: int, total: int) -> int:
    """随机选一首，尽量避开当前曲目。"""
    if total <= 1:
        return 0
    if current < 0:
        return random.randrange(total)
    idx = random.randrange(total - 1)
    return idx if idx < current else idx + 1


def next_index(
    mode: PlayMode, current: int, total: int, *, auto: bool = False
) -> int | None:
    """计算下一首曲目索引；``None`` 表示列表已播完。

    顺序播放时手动切歌始终循环，自动播完列表则停止。
    """
    if total <= 0:
        return None
    if mode == PlayMode.LOOP_ONE:
        return current
    if mode == PlayMode.SHUFFLE:
        return _shuffle_index(current, total)
    if not auto:
        return (current + 1) % total if current >= 0 else 0
    nxt = current + 1
    return nxt if nxt < total else None


def prev_index(mode: PlayMode, current: int, total: int) -> int | None:
    """计算上一首曲目索引，同样遵循播放模式。"""
    if total <= 0:
        return None
    if mode == PlayMode.LOOP_ONE:
        return current
    if mode == PlayMode.SHUFFLE:
        return _shuffle_index(current, total)
    idx = current if current >= 0 else 0
    return (idx - 1) % total


# ── 服务 ── #


class PlaybackService:
    """播放列表与播放控制。

    Args:
        engine_factory: 用本服务（作为引擎观察者）构造音频引擎。
        observer: 状态上报对象（通常是视图模型）。
        volume: 初始音量（0~1）。
        speed: 初始倍速。
    """

    def __init__(
        self,
        engine_factory: EngineFactory,
        observer: PlaybackObserver,
        *,
        volume: float = 0.7,
        speed: float = 1.0,
    ) -> None:
        self._observer = observer
        self._tracks: list[Track] = []
        self._current = -1
        self._mode = PlayMode.SEQUENCE
        self._volume = max(0.0, min(1.0, float(volume)))
        self._speed = float(speed)
        self._engine = engine_factory(self)

    # —— 状态 —— #

    @property
    def tracks(self) -> list[Track]:
        """当前播放列表。"""
        return self._tracks

    @property
    def current(self) -> int:
        """当前曲目索引；``-1`` 表示尚未选曲。"""
        return self._current

    @property
    def mode(self) -> PlayMode:
        """当前播放模式。"""
        return self._mode

    @property
    def volume(self) -> float:
        """当前音量（0~1）。"""
        return self._volume

    @property
    def speed(self) -> float:
        """当前倍速。"""
        return self._speed

    @property
    def playing(self) -> bool:
        """引擎当前是否在播放。"""
        return self._engine.playing

    def set_tracks(self, tracks: list[Track]) -> None:
        """整体替换播放列表（不改变实际播放状态）。"""
        self._tracks = tracks
        self._current = -1 if not tracks else 0

    # —— 控制 —— #

    async def play_at(self, index: int) -> None:
        """播放指定索引的曲目（越界时无副作用）。"""
        if not (0 <= index < len(self._tracks)):
            return
        self._current = index
        track = self._tracks[index]
        self._observer.on_duration(track.duration)
        self._observer.on_position(0.0)
        await self._engine.load(track.path, autoplay=True)
        self._observer.on_track_change(index)

    async def toggle(self) -> None:
        """播放 / 暂停切换；尚未选曲时从第一首开始。"""
        if self._current < 0:
            if self._tracks:
                await self.play_at(0)
            return
        await self._engine.set_paused(self._engine.playing)

    async def next(self, auto: bool = False) -> None:
        """下一首；顺序播放自动播完列表时停止。"""
        target = next_index(self._mode, self._current, len(self._tracks), auto=auto)
        if target is None:
            self._observer.on_play_state(False)
            return
        await self.play_at(target)

    async def prev(self) -> None:
        """上一首。"""
        target = prev_index(self._mode, self._current, len(self._tracks))
        if target is None:
            return
        await self.play_at(target)

    async def seek(self, seconds: float) -> None:
        """跳转到指定秒数。"""
        await self._engine.seek(seconds)

    def set_volume(self, value: float) -> None:
        """设置音量（夹紧到 0~1）。"""
        self._volume = max(0.0, min(1.0, float(value)))
        self._engine.set_volume(self._volume)

    def set_speed(self, value: float) -> None:
        """设置播放倍速（夹紧到合法范围）。"""
        self._speed = max(SPEED_MIN, min(SPEED_MAX, float(value)))
        self._engine.set_speed(self._speed)

    def cycle_mode(self) -> PlayMode:
        """按「顺序 → 单曲 → 随机」循环切换，返回新模式。"""
        self._mode = MODE_ORDER[(MODE_ORDER.index(self._mode) + 1) % len(MODE_ORDER)]
        return self._mode

    def shutdown(self) -> None:
        """释放引擎资源。"""
        self._engine.dispose()

    # —— AudioEngineObserver —— #

    def on_position(self, seconds: float) -> None:
        """转发播放进度。"""
        self._observer.on_position(seconds)

    def on_duration(self, seconds: float) -> None:
        """转发曲目时长。"""
        self._observer.on_duration(seconds)

    def on_play_state(self, playing: bool) -> None:
        """转发播放 / 暂停状态。"""
        self._observer.on_play_state(playing)

    def on_completed(self) -> None:
        """自然播放结束 → 自动切下一首（异步，避免阻塞事件回调）。"""
        asyncio.create_task(self.next(auto=True))
