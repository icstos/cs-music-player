"""音频播放器核心：数据模型、曲目加载、播放控制。"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import flet as ft
import flet_audio as fa

from .constants import (
    MODE_ORDER,
    MODE_SEQUENCE,
    MODE_LOOP_ONE,
    MODE_SHUFFLE,
    SUPPORTED_FORMATS,
)


# ── 数据模型 ── #


@dataclass
class Track:
    path: Path
    title: str = ""
    duration: float = 0.0

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.path.stem


@dataclass
class PlayerCallbacks:
    """播放器 → UI 的回调接口。"""

    on_position: Callable[[float], None]
    on_duration: Callable[[float], None]
    on_play_state: Callable[[bool], None]
    on_track_change: Callable[[int], None]


# ── 工具函数 ── #


def get_track_duration(path: Path) -> float:
    """用 mutagen 读取音频时长（秒），失败返回 0。"""
    try:
        from mutagen import File

        audio = File(str(path))
        if audio is not None and hasattr(audio, "info"):
            return float(audio.info.length)
    except Exception:
        pass
    return 0.0


def load_tracks_from_directory(directory: Path) -> list[Track]:
    """扫描目录下的音频文件，返回按文件名排序的 Track 列表。"""
    return [
        Track(path=f, duration=get_track_duration(f))
        for f in sorted(directory.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
    ]


# ── 播放器 ── #


class Player:
    """基于 flet-audio 的播放器。

    Windows 上 ``audio.play()`` 会超时，因此切歌时通过重建
    ``Audio`` 控件（autoplay=True）触发播放；
    pause / resume / seek 直接 await 即可。
    """

    def __init__(self, callbacks: PlayerCallbacks, page: ft.Page) -> None:
        self._cb = callbacks
        self._page = page
        self.tracks: list[Track] = []
        self.current: int = -1
        self.mode: str = MODE_SEQUENCE
        self._playing = False
        self._volume = 0.7
        self._audio: fa.Audio | None = None

    # —— Audio 控件生命周期 —— #

    def _new_audio(self, src: str) -> fa.Audio:
        return fa.Audio(
            src=src,
            autoplay=True,
            volume=self._volume,
            on_state_change=self._on_state,
            on_duration_change=self._on_duration,
            on_position_change=self._on_position,
        )

    def _remount(self, audio: fa.Audio) -> None:
        """替换 page.services 中的 Audio 控件。"""
        if self._audio is not None:
            try:
                self._page.services.remove(self._audio)
            except ValueError:
                pass
        self._audio = audio
        self._page.services.append(audio)
        self._page.update()

    # —— flet-audio 事件回调 —— #

    def _on_position(self, e) -> None:
        self._cb.on_position(e.position / 1000.0)

    def _on_duration(self, e) -> None:
        dur = e.duration
        seconds = dur.in_seconds if hasattr(dur, "in_seconds") else 0.0
        self._cb.on_duration(float(seconds))

    def _on_state(self, e) -> None:
        state = e.state
        if state == fa.AudioState.PLAYING:
            self._playing = True
            self._cb.on_play_state(True)
        elif state == fa.AudioState.PAUSED:
            self._playing = False
            self._cb.on_play_state(False)
        elif state == fa.AudioState.COMPLETED:
            self._playing = False
            self._cb.on_play_state(False)
            asyncio.create_task(self.next(auto=True))

    # —— 曲目索引计算 —— #

    def set_tracks(self, tracks: list[Track]) -> None:
        self.tracks = tracks
        self.current = -1 if not tracks else 0

    def _next_index(self, auto: bool) -> int | None:
        """计算下一首曲目索引。手动切换始终循环；自动切换视模式而定。"""
        if not self.tracks:
            return None
        if not auto:
            return (self.current + 1) % len(self.tracks) if self.current >= 0 else 0
        if self.mode == MODE_LOOP_ONE:
            return self.current
        if self.mode == MODE_SHUFFLE:
            if len(self.tracks) == 1:
                return self.current
            idx = random.randrange(len(self.tracks) - 1)
            return idx if idx < self.current else idx + 1
        nxt = self.current + 1
        return nxt if nxt < len(self.tracks) else None

    # —— 播放控制 —— #

    async def play_at(self, index: int) -> None:
        if not (0 <= index < len(self.tracks)):
            return
        self.current = index
        track = self.tracks[index]
        self._cb.on_duration(get_track_duration(track.path))
        self._cb.on_position(0.0)
        self._remount(self._new_audio(str(track.path)))
        self._cb.on_track_change(index)

    async def toggle(self) -> None:
        if self.current < 0:
            if self.tracks:
                await self.play_at(0)
            return
        if self._audio is None:
            return
        if self._playing:
            await self._audio.pause()
        else:
            await self._audio.resume()

    async def next(self, auto: bool = False) -> None:
        target = self._next_index(auto)
        if target is None:
            self._cb.on_play_state(False)
            return
        await self.play_at(target)

    async def prev(self) -> None:
        if not self.tracks:
            return
        idx = self.current if self.current >= 0 else 0
        await self.play_at((idx - 1) % len(self.tracks))

    async def seek(self, seconds: float) -> None:
        if self._audio is not None:
            try:
                await self._audio.seek(ft.Duration(seconds=seconds))
            except Exception:
                pass

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))
        if self._audio is not None:
            self._audio.volume = self._volume
            self._audio.update()

    def cycle_mode(self) -> str:
        self.mode = MODE_ORDER[(MODE_ORDER.index(self.mode) + 1) % len(MODE_ORDER)]
        return self.mode

    def shutdown(self) -> None:
        if self._audio is not None:
            try:
                self._page.services.remove(self._audio)
                self._page.update()
            except Exception:
                pass
            self._audio = None
