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
    """明暗模式；取值即持久化标识。"""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


#: 循环切换顺序（浅色 → 深色 → 跟随系统）。
THEME_MODES: tuple[ThemeMode, ...] = (
    ThemeMode.LIGHT,
    ThemeMode.DARK,
    ThemeMode.SYSTEM,
)


class ColorTheme(StrEnum):
    """配色主题；取值即持久化标识（已发布的字符串不要改）。

    定义顺序就是选择面板里的展示顺序，也是循环切换的顺序。
    """

    BUSINESS_BLUE = "business-blue"
    LAVENDER = "lavender"
    CORAL = "coral"
    MINT = "mint"
    VIVID_ORANGE = "vivid-orange"
    TIFFANY = "tiffany"
    SAKURA = "sakura"
    MINIMAL_WHITE = "minimal-white"
    PREMIUM_GRAY = "premium-gray"
    MIDNIGHT = "midnight"


#: 全部配色（顺序即展示顺序）。
COLOR_THEMES: tuple[ColorTheme, ...] = tuple(ColorTheme)

#: 首次启动的配色。
DEFAULT_COLOR_THEME: ColorTheme = ColorTheme.BUSINESS_BLUE

#: 名字本身就暗示了明暗的配色：选中时顺带切到对应外观。
#:
#: 两者是**正交**的维度——配色决定色相，外观决定明暗——所以这里只给
#: 「极简白 / 暗夜黑」这类带明确倾向的配色一个更符合直觉的默认外观；
#: 其余配色沿用用户当前的外观设置。
THEME_PREFERRED_MODE: dict[ColorTheme, ThemeMode] = {
    ColorTheme.MINIMAL_WHITE: ThemeMode.LIGHT,
    ColorTheme.MIDNIGHT: ThemeMode.DARK,
}


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
