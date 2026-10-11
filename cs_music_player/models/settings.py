"""用户设置相关的数据结构与枚举。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .constants import (
    DESKTOP_LYRIC_FONT_DEFAULT,
    DESKTOP_LYRIC_FONT_MAX,
    DESKTOP_LYRIC_FONT_MIN,
    LYRIC_FONT_MAX,
    LYRIC_FONT_MIN,
)


def clamp_lyric_font(size: float) -> float:
    """把主界面歌词字号夹紧到合法区间（保留一位小数）。"""
    return round(min(LYRIC_FONT_MAX, max(LYRIC_FONT_MIN, float(size))), 1)


def clamp_desktop_lyric_font(size: float) -> float:
    """把桌面歌词字号夹紧到合法区间（保留一位小数）。"""
    return round(
        min(DESKTOP_LYRIC_FONT_MAX, max(DESKTOP_LYRIC_FONT_MIN, float(size))), 1
    )


class ThemeMode(StrEnum):
    """主题模式；取值即持久化标识。"""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


#: 循环切换顺序（浅色 → 深色 → 跟随系统）。
THEME_MODES: tuple[ThemeMode, ...] = (
    ThemeMode.LIGHT,
    ThemeMode.DARK,
    ThemeMode.SYSTEM,
)


@dataclass
class DesktopLyricConfig:
    """桌面歌词的持久化配置。"""

    enabled: bool = False
    locked: bool = False
    font_size: float = DESKTOP_LYRIC_FONT_DEFAULT
    #: 窗口左上角（物理像素，屏幕坐标）；``None`` 表示用默认位置。
    x: float | None = None
    y: float | None = None

    def clamp_font(self) -> None:
        """就地夹紧字号（规则见 :func:`clamp_desktop_lyric_font`）。"""
        self.font_size = clamp_desktop_lyric_font(self.font_size)
