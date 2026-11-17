"""设置服务：主题模式、歌词字号、桌面歌词配置的读写与取值约束。

只依赖 ``PreferencesPort``；所有持久化格式与旧版 ``store.py`` 完全一致，
升级后用户设置原样保留。
"""

from __future__ import annotations

import json

from ..infra.ports import (
    COLOR_THEME_KEY,
    DESKTOP_LYRIC_KEY,
    LYRIC_FONT_KEY,
    THEME_MODE_KEY,
    PreferencesPort,
)
from ..models import (
    DEFAULT_COLOR_THEME,
    DESKTOP_LYRIC_FONT_DEFAULT,
    DESKTOP_LYRIC_FONT_MAX,
    DESKTOP_LYRIC_FONT_MIN,
    LYRIC_FONT_DEFAULT,
    LYRIC_FONT_MAX,
    LYRIC_FONT_MIN,
    ColorTheme,
    DesktopLyricConfig,
    ThemeMode,
    clamp_lyric_font,
)

__all__ = ["SettingsService"]


class SettingsService:
    """用户设置的读写入口。"""

    def __init__(self, preferences: PreferencesPort) -> None:
        self._prefs = preferences

    # —— 主题 —— #

    async def theme_mode(self) -> ThemeMode:
        """读取主题模式，非法值回退为跟随系统。"""
        raw = await self._prefs.get(THEME_MODE_KEY)
        try:
            return ThemeMode(str(raw))
        except ValueError:
            return ThemeMode.SYSTEM

    async def save_theme_mode(self, mode: ThemeMode) -> None:
        """保存主题模式。"""
        await self._prefs.set(THEME_MODE_KEY, str(mode))

    async def color_theme(self) -> ColorTheme:
        """读取配色主题，未知标识回退为默认配色（例如降级回旧版本后）。"""
        raw = await self._prefs.get(COLOR_THEME_KEY)
        try:
            return ColorTheme(str(raw))
        except ValueError:
            return DEFAULT_COLOR_THEME

    async def save_color_theme(self, theme: ColorTheme) -> None:
        """保存配色主题。"""
        await self._prefs.set(COLOR_THEME_KEY, str(theme))

    # —— 歌词字号 —— #

    async def lyric_font(self) -> float:
        """读取歌词字号（全局设置），非法值回退为默认字号。"""
        raw = await self._prefs.get(LYRIC_FONT_KEY)
        if not isinstance(raw, (int, float, str)) or isinstance(raw, bool):
            return LYRIC_FONT_DEFAULT
        try:
            value = float(raw)
        except ValueError:
            return LYRIC_FONT_DEFAULT
        if not (LYRIC_FONT_MIN <= value <= LYRIC_FONT_MAX):
            return LYRIC_FONT_DEFAULT
        return value

    async def save_lyric_font(self, size: float) -> None:
        """保存歌词字号（全局设置）。"""
        await self._prefs.set(LYRIC_FONT_KEY, clamp_lyric_font(size))

    # —— 桌面歌词 —— #

    async def desktop_lyric(self) -> DesktopLyricConfig:
        """读取桌面歌词设置；缺失或损坏的字段按默认值补齐。"""
        raw = None
        try:
            raw = await self._prefs.get(DESKTOP_LYRIC_KEY)
        except Exception:
            raw = None

        data: dict = {}
        if isinstance(raw, str) and raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    data = parsed
            except (TypeError, ValueError):
                data = {}

        def _number(key: str) -> float | None:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            return None

        config = DesktopLyricConfig(
            enabled=bool(data.get("enabled", False)),
            locked=bool(data.get("locked", False)),
            font_size=DESKTOP_LYRIC_FONT_DEFAULT,
            x=_number("x"),
            y=_number("y"),
        )
        font = _number("font_size")
        if font is not None and DESKTOP_LYRIC_FONT_MIN <= font <= DESKTOP_LYRIC_FONT_MAX:
            config.font_size = font
        return config

    async def save_desktop_lyric(self, config: DesktopLyricConfig) -> None:
        """保存桌面歌词设置（整体覆盖）。"""
        payload = json.dumps(
            {
                "enabled": bool(config.enabled),
                "locked": bool(config.locked),
                "font_size": float(config.font_size),
                "x": config.x,
                "y": config.y,
            },
            ensure_ascii=False,
        )
        await self._prefs.set(DESKTOP_LYRIC_KEY, payload)
