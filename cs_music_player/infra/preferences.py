"""用户数据持久化的键名（在 ``infra.ports`` 里定义）与 Flet ``SharedPreferences``
适配器。

键名属于抽象契约的一部分，放在 :mod:`cs_music_player.infra.ports`；这里只
负责用 Flet 的实现去满足它。键名与旧版 ``store.py`` 完全一致（Flet 会在前面
加 ``flutter.`` 前缀），因此升级后用户的收藏、历史文件夹、主题、歌词偏移等
数据原样保留。
"""

from __future__ import annotations

import flet as ft

from .ports import (
    COLOR_THEME_KEY,
    DESKTOP_LYRIC_KEY,
    FAVORITES_KEY,
    LYRIC_FONT_KEY,
    LYRIC_OFFSETS_KEY,
    PINNED_FOLDERS_KEY,
    RECENT_FOLDERS_KEY,
    THEME_MODE_KEY,
)

__all__ = [
    "COLOR_THEME_KEY",
    "DESKTOP_LYRIC_KEY",
    "FAVORITES_KEY",
    "LYRIC_FONT_KEY",
    "LYRIC_OFFSETS_KEY",
    "PINNED_FOLDERS_KEY",
    "RECENT_FOLDERS_KEY",
    "THEME_MODE_KEY",
    "FletPreferences",
    "install_preferences",
]


class FletPreferences:
    """``ft.SharedPreferences`` 的最小包装，满足 ``PreferencesPort``。

    Flet 的实现本身就带 ``get`` / ``set`` 两个协程方法，这里显式包一层是
    为了给上层一个稳定的、不随 Flet 版本变化的契约。
    """

    def __init__(self, inner: ft.SharedPreferences | None = None) -> None:
        self._inner = inner if inner is not None else ft.SharedPreferences()

    @property
    def control(self) -> ft.SharedPreferences:
        """底层 Flet 服务控件（需要挂到 ``page.services`` 上）。"""
        return self._inner

    async def get(self, key: str) -> object | None:
        """读取一个键；不存在返回 ``None``。"""
        return await self._inner.get(key)

    async def set(self, key: str, value: object) -> None:
        """写入一个键。"""
        await self._inner.set(key, value)


def install_preferences(page: ft.Page) -> FletPreferences:
    """创建并挂载 ``SharedPreferences`` 服务，返回可用实例。"""
    prefs = FletPreferences()
    page.services.append(prefs.control)
    return prefs
