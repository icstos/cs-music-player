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

#: 配色 → 品牌色种子。
#:
#: **一条配色只声明一个色值**：明暗两套（46 个 M3 角色）由 cs-ui 的色板引擎
#: 从这个种子解算 —— 主色的明度按对比度求，中性表面掺一点同色相，深色档位
#: 单独排布。所以这里不再写「底色 / 描边 / 各种灰」，也不会出现某个配色忘了
#: 深色版的情况。
#:
#: 取值沿用各配色原来的主色，保证「商务蓝还是那个蓝」。深色模式要换主色时，
#: 引擎会把种子按暗底重新解明度（例如极简白的近黑主色在暗色下变成雾白）。
THEME_SEEDS: dict[ColorTheme, str] = {
    ColorTheme.BUSINESS_BLUE: "#2563eb",
    ColorTheme.LAVENDER: "#7c5cf5",
    ColorTheme.CORAL: "#e05445",
    ColorTheme.MINT: "#0ba36b",
    ColorTheme.VIVID_ORANGE: "#f2760c",
    ColorTheme.TIFFANY: "#0da3a0",
    ColorTheme.SAKURA: "#e0518c",
    ColorTheme.MINIMAL_WHITE: "#18181b",
    ColorTheme.PREMIUM_GRAY: "#475569",
    ColorTheme.MIDNIGHT: "#1f2937",
}

#: 配色 → 显示名（选择面板与提示文案共用；顺序即枚举顺序）。
THEME_NAMES: dict[ColorTheme, str] = {
    ColorTheme.BUSINESS_BLUE: "商务蓝",
    ColorTheme.LAVENDER: "薰衣草紫",
    ColorTheme.CORAL: "珊瑚红",
    ColorTheme.MINT: "薄荷绿",
    ColorTheme.VIVID_ORANGE: "活力橙",
    ColorTheme.TIFFANY: "蒂芙尼蓝",
    ColorTheme.SAKURA: "樱花粉",
    ColorTheme.MINIMAL_WHITE: "极简白",
    ColorTheme.PREMIUM_GRAY: "高级灰",
    ColorTheme.MIDNIGHT: "暗夜黑",
}

#: 首次启动的配色种子（供启动路径在读到持久化设置前先把窗口画对）。
DEFAULT_THEME_SEED: str = THEME_SEEDS[DEFAULT_COLOR_THEME]


def seed_of(theme: ColorTheme) -> str:
    """取配色的品牌色种子；未知标识（例如旧版本存下的值）回退到默认配色。"""
    return THEME_SEEDS.get(theme, DEFAULT_THEME_SEED)


def name_of(theme: ColorTheme) -> str:
    """取配色的显示名；未知标识同样回退到默认配色的名字。"""
    return THEME_NAMES.get(theme, THEME_NAMES[DEFAULT_COLOR_THEME])



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
