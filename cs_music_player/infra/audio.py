"""基于 ``flet-audio`` 的音频引擎。

实现 :class:`cs_music_player.infra.ports.AudioEnginePort`。这里封着两个
和 Flet 强相关的技术细节：

1. **Windows 上 ``audio.play()`` 会超时**，所以切歌时通过重建 ``Audio``
   控件（``autoplay=True``）触发播放；``pause`` / ``resume`` / ``seek``
   直接 ``await`` 即可。
2. 音量与倍速是「引擎属性」而不是控件属性：重建控件时必须把当前值带过去。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import flet as ft
import flet_audio as fa

from .ports import AudioEngineObserver

__all__ = ["FletAudioEngine"]


class FletAudioEngine:
    """把 ``flet_audio.Audio`` 的控件生命周期收敛成一个引擎对象。

    Args:
        page: Flet 页面；``Audio`` 控件挂在 ``page.services`` 上。
        observer: 播放事件的上报对象。
        volume: 初始音量（0~1）。
        speed: 初始倍速。
    """

    def __init__(
        self,
        page: ft.Page,
        observer: AudioEngineObserver,
        *,
        volume: float = 0.7,
        speed: float = 1.0,
    ) -> None:
        self._page = page
        self._observer = observer
        self._playing = False
        self._volume = max(0.0, min(1.0, float(volume)))
        self._speed = float(speed)
        self._audio: fa.Audio | None = None

    # —— AudioEnginePort —— #

    @property
    def playing(self) -> bool:
        """引擎当前是否处于播放状态（由 flet-audio 的状态事件维护）。"""
        return self._playing

    def set_volume(self, value: float) -> None:
        """设置音量（夹紧到 0~1）并实时应用到当前音频。"""
        self._volume = max(0.0, min(1.0, float(value)))
        if self._audio is not None:
            self._audio.volume = self._volume
            self._audio.update()

    def set_speed(self, value: float) -> None:
        """设置播放倍速并实时应用到当前音频。"""
        self._speed = float(value)
        if self._audio is not None:
            self._audio.playback_rate = self._speed
            self._audio.update()

    async def load(self, path: Path, *, autoplay: bool = True) -> None:
        """装载曲目；``autoplay`` 为真时立即开始播放。"""
        self._playing = False
        self._remount(self._new_audio(str(path), autoplay=autoplay))

    async def set_paused(self, paused: bool) -> None:
        """暂停 / 继续；尚无音频时为空操作。"""
        if self._audio is None:
            return
        if paused:
            await self._audio.pause()
        else:
            await self._audio.resume()

    async def seek(self, seconds: float) -> None:
        """跳转到指定秒数；失败静默（例如尚未装载音频或后端不支持）。"""
        if self._audio is not None:
            try:
                await self._audio.seek(ft.Duration(seconds=seconds))
            except Exception:
                pass

    def dispose(self) -> None:
        """把 ``Audio`` 控件从 ``page.services`` 摘掉（重复调用无副作用）。"""
        audio, self._audio = self._audio, None
        if audio is not None:
            try:
                self._page.services.remove(audio)
                self._page.update()
            except Exception:
                pass

    # —— 内部：控件生命周期 —— #

    def _new_audio(self, src: str, *, autoplay: bool) -> fa.Audio:
        return fa.Audio(
            src=src,
            autoplay=autoplay,
            volume=self._volume,
            playback_rate=self._speed,
            on_state_change=self._on_state,
            on_duration_change=self._on_duration,
            on_position_change=self._on_position,
        )

    def _remount(self, audio: fa.Audio) -> None:
        """用新控件替换 ``page.services`` 里的旧控件。"""
        if self._audio is not None:
            try:
                self._page.services.remove(self._audio)
            except ValueError:
                pass
        self._audio = audio
        self._page.services.append(audio)
        self._page.update()

    # —— 内部：flet-audio 事件回调 —— #

    def _on_position(self, e: Any) -> None:
        self._observer.on_position(e.position / 1000.0)

    def _on_duration(self, e: Any) -> None:
        duration = e.duration
        seconds = duration.in_seconds if hasattr(duration, "in_seconds") else 0.0
        self._observer.on_duration(float(seconds))

    def _on_state(self, e: Any) -> None:
        state = e.state
        if state == fa.AudioState.PLAYING:
            self._playing = True
            self._observer.on_play_state(True)
        elif state == fa.AudioState.PAUSED:
            self._playing = False
            self._observer.on_play_state(False)
        elif state == fa.AudioState.COMPLETED:
            self._playing = False
            self._observer.on_play_state(False)
            asyncio.create_task(self._notify_completed())

    async def _notify_completed(self) -> None:
        """把「自然播放结束」异步转发出去（与原实现一致地不阻塞事件回调）。"""
        self._observer.on_completed()
