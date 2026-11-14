"""基于 ``flet-audio`` 的音频引擎。

实现 :class:`cs_music_player.infra.ports.AudioEnginePort`。

**这个文件从 cs-ui 接过了「音频」这件事**。cs-ui 是界面构件库，播放要接管时间轴、
设备与队列，属于应用而不是控件，所以 ``ui.display.media.Audio`` 已经下线；它当年
解决的三件事现在由本模块负责：

1. **服务挂载**——``flet_audio.Audio`` 继承 ``ft.Service`` 而不是 ``ft.Control``，
   放进控件树会被 Flutter 判成 ``Unknown control: Audio``，只能挂 ``page.services``；
   挂载点由 :class:`_ServiceHost` 这个最小契约描述（测试里换成两行假对象即可）。
2. **事件转发**——``state`` / ``position`` / ``duration`` 三个回调直接翻成
   :class:`AudioEngineObserver` 的方法调用，业务层不认识 ``flet_audio`` 的类型。
3. **状态跨重建**——音量和倍速是「引擎属性」而不是控件属性，重建控件时必须带过去。

还有一个 Windows 上的坑：``audio.play()`` 会超时，所以切歌不调 ``play()``，而是
重建控件并带上 ``autoplay=True``；``pause`` / ``resume`` / ``seek`` 直接 ``await``。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import flet as ft
import flet_audio as fa

from .ports import AudioEngineObserver

__all__ = ["FletAudioEngine"]


class _ServiceHost(Protocol):
    """引擎对「页面」的全部要求。

    只声明真正用到的两样东西：``services`` 列表（``flet_audio.Audio`` 的挂载点）
    与 ``update()``。这样单测不必造一个 ``ft.Page``，也就不必起客户端。
    """

    services: list[Any]

    def update(self) -> None:
        """把补丁下发给客户端。"""
        ...


class FletAudioEngine:
    """把 ``flet_audio.Audio`` 的控件生命周期收敛成一个引擎对象。

    Args:
        page: 页面（满足 :class:`_ServiceHost` 即可）。
        observer: 播放事件的上报对象。
        volume: 初始音量（0~1），越界夹紧。
        speed: 初始倍速。
        audio_factory: 控件工厂，默认 ``flet_audio.Audio``；单测注入假控件即可
            验证「挂载 / 摘除 / 状态带过去」而不触碰真实音频设备。
    """

    def __init__(
        self,
        page: _ServiceHost,
        observer: AudioEngineObserver,
        *,
        volume: float = 0.7,
        speed: float = 1.0,
        audio_factory: Callable[..., Any] = fa.Audio,
    ) -> None:
        self._page = page
        self._observer = observer
        self._audio_factory = audio_factory
        self._playing = False
        self._volume = _clamp_volume(volume)
        self._speed = float(speed)
        self._audio: Any | None = None

    # —— AudioEnginePort —— #

    @property
    def playing(self) -> bool:
        """引擎当前是否处于播放状态（由 flet-audio 的状态事件维护）。"""
        return self._playing

    @property
    def volume(self) -> float:
        """当前音量（0~1），切歌重建后仍然是这个值。"""
        return self._volume

    @property
    def speed(self) -> float:
        """当前倍速，切歌重建后仍然是这个值。"""
        return self._speed

    def set_volume(self, value: float) -> None:
        """设置音量（夹紧到 0~1）并实时应用到当前音频。"""
        self._volume = _clamp_volume(value)
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
        """装载曲目；``autoplay`` 为真时立即开始播放。

        用「重建控件 + autoplay」代替 ``play()``：Windows 上后者会超时。

        播 / 停**由意图直接定**，不等控件事件：实测 Windows 上带
        ``autoplay=True`` 挂载时，``PLAYING`` 事件可能在控件进 ``services``
        之前就发完了，界面会一直以为自己在暂停。事件仍然接（见
        :meth:`_on_state`），只是降级成「校正」而不是唯一真相。
        """
        self._mount(str(path), autoplay=autoplay)
        self._set_playing(autoplay)

    async def set_paused(self, paused: bool) -> None:
        """暂停 / 继续；尚无音频时为空操作。"""
        if self._audio is None:
            return
        if paused:
            await self._audio.pause()
        else:
            await self._audio.resume()
        self._set_playing(not paused)

    async def seek(self, seconds: float) -> None:
        """跳转到指定秒数；失败静默（例如尚未装载音频或后端不支持）。

        **用毫秒构造**而不是 ``ft.Duration(seconds=...)``：后者的 ``in_seconds``
        会把小数截断（12.5s → 12.0s），而拖进度条本来就常落在半秒上。
        """
        if self._audio is None:
            return
        try:
            await self._audio.seek(ft.Duration(milliseconds=round(seconds * 1000)))
        except Exception:
            pass

    def dispose(self) -> None:
        """把音频控件从 ``page.services`` 摘掉（重复调用无副作用）。"""
        audio, self._audio = self._audio, None
        self._playing = False
        if audio is None:
            return
        try:
            self._page.services.remove(audio)
            self._page.update()
        except Exception:
            pass

    # —— 内部：控件生命周期 —— #

    def _set_playing(self, playing: bool) -> None:
        """记录播放状态；**只在真的变化时**上报，重复事件不会多刷一帧。"""
        playing = bool(playing)
        if self._playing == playing:
            return
        self._playing = playing
        self._observer.on_play_state(playing)

    def _mount(self, src: str, *, autoplay: bool) -> None:
        """用新控件替换 ``page.services`` 里的旧控件。"""
        audio = self._new_audio(src, autoplay=autoplay)
        if self._audio is not None:
            try:
                self._page.services.remove(self._audio)
            except ValueError:
                pass
        self._audio = audio
        self._page.services.append(audio)
        self._page.update()

    def _new_audio(self, src: str, *, autoplay: bool) -> Any:
        """构造音频控件；音量 / 倍速 / 回调都在这里一次性带上。

        三个回调绑定的是**本引擎**的方法而不是 lambda：控件被重建后，旧控件
        仍可能吐最后一帧事件，绑定方法两边都能接住，也不会多留一份闭包引用。
        """
        return self._audio_factory(
            src=src,
            autoplay=autoplay,
            volume=self._volume,
            playback_rate=self._speed,
            on_state_change=self._on_state,
            on_duration_change=self._on_duration,
            on_position_change=self._on_position,
        )

    # —— 内部：flet-audio 事件回调 —— #

    def _on_position(self, e: Any) -> None:
        self._observer.on_position(e.position / 1000.0)

    def _on_duration(self, e: Any) -> None:
        """把 ``ft.Duration`` 换算成秒；走毫秒是因为 ``in_seconds`` 会截断小数。"""
        duration = e.duration
        milliseconds = getattr(duration, "in_milliseconds", None)
        if milliseconds is not None:
            self._observer.on_duration(float(milliseconds) / 1000.0)
        else:
            self._observer.on_duration(0.0)

    def _on_state(self, e: Any) -> None:
        state = e.state
        if state == fa.AudioState.PLAYING:
            self._set_playing(True)
        elif state in (fa.AudioState.PAUSED, fa.AudioState.COMPLETED):
            self._set_playing(False)
            if state == fa.AudioState.COMPLETED:
                self._observer.on_completed()


def _clamp_volume(value: float) -> float:
    """把任意输入夹到 0~1；``NaN`` 退回 0（避免把 NaN 传给音频后端）。"""
    number = float(value)
    if number != number:  # NaN
        return 0.0
    return max(0.0, min(1.0, number))
