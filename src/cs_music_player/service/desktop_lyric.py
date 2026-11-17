"""桌面歌词服务：悬浮窗生命周期、配置持久化与画面推送。

浮窗自身跑在独立线程上，回调经由组装根注入的 ``Dispatcher`` 回到 UI 事件
循环，因此本服务（以及它上层的视图模型）始终是单线程的。

本服务**不反向调用播放器**：悬浮窗上的播放控制键只是把命令广播给订阅者
（视图模型），由后者驱动播放服务——单向依赖得以保持。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from ..infra.ports import DesktopLyricPort
from ..models import (
    DESKTOP_LYRIC_FONT_DEFAULT,
    DesktopLyricConfig,
    clamp_desktop_lyric_font,
)
from .settings import SettingsService

__all__ = ["DesktopLyricFactory", "DesktopLyricListener", "DesktopLyricService"]

#: 用「命令回调 + 配置回调」造一个悬浮窗控制器。
DesktopLyricFactory = Callable[
    [Callable[[str], None], Callable[[DesktopLyricConfig], None]],
    DesktopLyricPort,
]


@runtime_checkable
class DesktopLyricListener(Protocol):
    """桌面歌词悬浮窗的事件订阅者。"""

    def on_desktop_command(self, name: str) -> None:
        """用户在悬浮窗上按了播放控制键（``prev`` / ``toggle`` / ``next``）。"""
        ...

    def on_desktop_config(self, config: DesktopLyricConfig) -> None:
        """悬浮窗配置变化（显隐 / 锁定 / 字号 / 位置）。"""
        ...


class DesktopLyricService:
    """把悬浮窗的读写、持久化与事件广播编排在一起。

    Args:
        factory: 构造悬浮窗控制器（组装根注入，内部包好跨线程调度）。
        settings: 配置的持久化。
    """

    def __init__(self, factory: DesktopLyricFactory, settings: SettingsService) -> None:
        self._settings = settings
        self._listeners: list[DesktopLyricListener] = []
        self._controller = factory(self._handle_command, self._handle_config)

    # —— 订阅 —— #

    def subscribe(self, listener: DesktopLyricListener) -> Callable[[], None]:
        """订阅悬浮窗事件，返回取消订阅的函数。"""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    # —— 状态 —— #

    @property
    def config(self) -> DesktopLyricConfig:
        """当前配置。"""
        return self._controller.config

    # —— 生命周期 —— #

    async def restore(self) -> DesktopLyricConfig:
        """把持久化的配置灌回悬浮窗（启动时调用一次）。"""
        config = await self._settings.desktop_lyric()
        self._controller.apply_config(config)
        return config

    def stop(self) -> None:
        """关闭悬浮窗并结束窗口线程。"""
        self._controller.stop()

    # —— 操作（主界面入口）—— #

    def set_visible(self, visible: bool) -> None:
        """显示 / 隐藏悬浮窗。"""
        self._controller.set_visible(visible)
        self._notify_config()

    def toggle_visible(self) -> bool:
        """切换显隐，返回切换后的状态。"""
        enabled = not self._controller.config.enabled
        self._controller.set_visible(enabled)
        self._notify_config()
        return enabled

    def set_locked(self, locked: bool) -> None:
        """锁定（鼠标穿透）/ 解锁悬浮窗。"""
        self._controller.set_locked(locked)
        self._notify_config()

    def toggle_locked(self) -> bool:
        """切换锁定状态，返回切换后的状态。"""
        locked = not self._controller.config.locked
        self._controller.set_locked(locked)
        self._notify_config()
        return locked

    def set_font_size(self, size: float) -> None:
        """设置悬浮窗字号（夹紧到合法区间）。"""
        self._controller.set_font_size(clamp_desktop_lyric_font(size))
        self._notify_config()

    def nudge_font(self, delta: float) -> None:
        """在当前字号上增减一段。"""
        self.set_font_size(self._controller.config.font_size + delta)

    def reset_font(self) -> None:
        """恢复默认字号。"""
        self.set_font_size(DESKTOP_LYRIC_FONT_DEFAULT)

    def center(self) -> None:
        """回到默认停放位置。"""
        self._controller.center()
        self._notify_config()

    # —— 画面推送 —— #

    def push(self, lines: Sequence[str], active: int, playing: bool) -> None:
        """把歌词、当前行与播放状态推给悬浮窗（值未变时控制器自行忽略）。"""
        self._controller.set_lyrics(lines)
        self._controller.set_active(active)
        self._controller.set_playing(playing)

    # —— 内部：悬浮窗回调（已回到事件循环）—— #

    def _handle_command(self, name: str) -> None:
        for listener in list(self._listeners):
            try:
                listener.on_desktop_command(name)
            except Exception:
                pass

    def _handle_config(self, config: DesktopLyricConfig) -> None:
        """悬浮窗自己改了配置（拖动、右键菜单）→ 持久化并通知订阅者。"""
        asyncio.create_task(self._settings.save_desktop_lyric(config))
        self._notify_config(config)

    def _notify_config(self, config: DesktopLyricConfig | None = None) -> None:
        """把当前配置广播给订阅者。

        主界面入口（开关 / 锁定 / 字号）改完配置后也走这里，而不是依赖控制器
        把同一个值回传——悬浮窗是异步线程，回传顺序不可依赖。
        """
        current = config if config is not None else self._controller.config
        for listener in list(self._listeners):
            try:
                listener.on_desktop_config(current)
            except Exception:
                pass
