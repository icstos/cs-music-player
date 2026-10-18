"""配色系统：从「一小撮色值」推导出整套界面令牌（纯 Python，不依赖 Flet）。

设计意图
--------

配色是**两个正交维度**：

- :class:`~cs_music_player.models.ColorTheme` —— 色相（商务蓝、薰衣草紫……）；
- :class:`~cs_music_player.models.ThemeMode` —— 明暗（浅色 / 深色 / 跟随系统）。

于是每个配色只需声明自己的「主色 + 强调色 + 染色强度」，剩下十几个令牌
（背景、卡片、描边、文字灰阶、反色文字……）由 :func:`build_palette` 用
同一套规则推导。好处：

- 加一个配色 = 加一行 :class:`ThemeSpec`，不用手抄 20 个色值；
- 亮 / 暗两套永远同源，不会出现「某个主题忘了暗色版」；
- 「主色上的文字」由对比度算出来（:func:`readable_on`），亮色主色上不会
  出现白字看不清的情况。

推导规则（浅色）：底色 = 白色混入少量主色，层级靠混入比例区分；深色同理，
以近黑为底。所有令牌都保证 ``TEXT_MAIN`` 与 ``BG`` 的对比度足够读。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import COLOR_THEMES, DEFAULT_COLOR_THEME, ColorTheme

__all__ = [
    "DEFAULT_SPEC",
    "PALETTE_KEYS",
    "THEME_SPECS",
    "ThemeSpec",
    "build_palette",
    "contrast_ratio",
    "mix",
    "readable_on",
    "spec_of",
]

Tokens = dict[str, str]

#: 一套调色板包含的全部令牌（顺序仅用于文档与测试断言）。
PALETTE_KEYS: tuple[str, ...] = (
    "PRIMARY",
    "PRIMARY_LIGHT",
    "PRIMARY_DARK",
    "PRIMARY_BG",
    "ACCENT",
    "ACCENT_LIGHT",
    "ON_PRIMARY",
    "ON_ACCENT",
    "BG",
    "SURFACE",
    "SURFACE_SOFT",
    "BORDER",
    "BORDER_FOCUS",
    "TEXT_MAIN",
    "TEXT_DIM",
    "TEXT_MUTED",
    "SCAFFOLD",
    "CANVAS",
    "CARD",
    "TOOLTIP_BG",
    "TOOLTIP_TEXT",
    "ERROR",
    "ON_ERROR",
)

#: 深浅两套的「锚色」：一个亮底、一个暗底。所有灰度都由它们派生。
_LIGHT_SURFACE = "#ffffff"
_DARK_BASE = "#0b0e14"
_ERROR_LIGHT = "#c0271b"
_ERROR_DARK = "#f87171"
_TEXT_INK = "#0f172a"
_MUTED_INK = "#8296ad"
_ON_LIGHT = "#ffffff"
_ON_DARK = "#10151f"


# ── 颜色运算 ── #


def _rgb(color: str) -> tuple[int, int, int]:
    """``#rrggbb`` → 三元组；非法输入回退为黑色（宁可难看，不要崩）。"""
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except (ValueError, IndexError):
        return 0, 0, 0


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(base: str, other: str, ratio: float) -> str:
    """把 ``other`` 按 ``ratio``（0~1）混进 ``base`` 并返回 ``#rrggbb``。"""
    ratio = max(0.0, min(1.0, ratio))
    a, b = _rgb(base), _rgb(other)
    return _hex(tuple(a[i] + (b[i] - a[i]) * ratio for i in range(3)))


def _linear(channel: int) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    """WCAG 相对亮度。"""
    r, g, b = (_linear(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first: str, second: str) -> float:
    """两个颜色的对比度（1~21，WCAG 口径）。"""
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def ensure_contrast(color: str, background: str, target: float = 4.0) -> str:
    """把颜色往黑里压，直到它在 ``background`` 上够读（WCAG 小字 AA ≈ 4.5）。

    主色/强调色既要铺色块、也要当**文字色**用（选中的序号、图标、开关标注）。
    浅色主题下「薄荷绿」「活力橙」这类明快的主色直接当小字用会发虚，所以这里
    统一压到目标对比度；压不上去就按 5% 步进压满，绝不返回比原色更浅的值。
    """
    result = color
    for step in range(1, 13):
        if contrast_ratio(result, background) >= target:
            break
        result = mix(color, "#000000", step * 0.05)
    return result


def readable_on(background: str) -> str:
    """在主色块上写字时该用深墨还是白字——取对比度更高的那个。"""
    return (
        _ON_DARK
        if contrast_ratio(background, _ON_DARK) >= contrast_ratio(background, _ON_LIGHT)
        else _ON_LIGHT
    )


# ── 配色声明 ── #


@dataclass(frozen=True)
class ThemeSpec:
    """一个配色的「最小声明」。

    只写这些就够了，其余令牌由 :func:`build_palette` 推导：

    Attributes:
        label: 选择面板上显示的名字。
        primary: 浅色下的主色（按钮、进度、选中态）。
        accent: 强调色（少量点缀：图标、定时器、收藏）。
        tint: 底色染色强度，0 表示完全不染色（纯灰阶）。
        dark_primary: 深色下的主色；缺省由 ``primary`` 混白推导。
        dark_accent: 深色下的强调色；缺省由 ``accent`` 混白推导。
        dark_base: 深色底色的锚色；缺省为统一的近黑蓝。
    """

    label: str
    primary: str
    accent: str
    tint: float = 0.045
    dark_primary: str | None = None
    dark_accent: str | None = None
    dark_base: str | None = None


#: 全部配色。加一个配色：先在 ``ColorTheme`` 里加成员，再在这里加一行。
THEME_SPECS: dict[ColorTheme, ThemeSpec] = {
    ColorTheme.BUSINESS_BLUE: ThemeSpec(
        "商务蓝", primary="#2563eb", accent="#0e7490", tint=0.045
    ),
    ColorTheme.LAVENDER: ThemeSpec(
        "薰衣草紫", primary="#7c5cf5", accent="#c026d3", tint=0.05
    ),
    ColorTheme.CORAL: ThemeSpec(
        "珊瑚红", primary="#e05445", accent="#d97706", tint=0.045
    ),
    ColorTheme.MINT: ThemeSpec(
        "薄荷绿", primary="#0ba36b", accent="#0ea5e9", tint=0.045
    ),
    ColorTheme.VIVID_ORANGE: ThemeSpec(
        "活力橙", primary="#f2760c", accent="#e11d48", tint=0.04
    ),
    ColorTheme.TIFFANY: ThemeSpec(
        "蒂芙尼蓝", primary="#0da3a0", accent="#1d4ed8", tint=0.045
    ),
    ColorTheme.SAKURA: ThemeSpec(
        "樱花粉", primary="#e0518c", accent="#8b5cf6", tint=0.05
    ),
    ColorTheme.MINIMAL_WHITE: ThemeSpec(
        "极简白",
        primary="#18181b",
        accent="#52525b",
        tint=0.03,
        dark_primary="#e4e4e7",
        dark_accent="#a1a1aa",
    ),
    ColorTheme.PREMIUM_GRAY: ThemeSpec(
        "高级灰", primary="#475569", accent="#0284c7", tint=0.04
    ),
    # 暗夜黑：深色底单独指定，主色在浅色下是石墨黑、深色下是雾白。
    ColorTheme.MIDNIGHT: ThemeSpec(
        "暗夜黑",
        primary="#1f2937",
        accent="#0284c7",
        tint=0.03,
        dark_primary="#e2e8f0",
        dark_accent="#38bdf8",
        dark_base="#07080b",
    ),
}

DEFAULT_SPEC: ThemeSpec = THEME_SPECS[DEFAULT_COLOR_THEME]


def spec_of(theme: ColorTheme) -> ThemeSpec:
    """取配色声明；未知标识回退到默认配色（与设置层的容错一致）。"""
    return THEME_SPECS.get(theme, DEFAULT_SPEC)


# ── 调色板推导 ── #


def _light(spec: ThemeSpec) -> Tokens:
    bg = mix(_LIGHT_SURFACE, spec.primary, spec.tint)
    # 底色由「原始主色」染色以保住色相，主色本身再按可读性压一档。
    # 目标取 4.6 而非 4.0：主色块上还要压白字，得留出「白字 ≥ 4.5」的余量。
    primary = ensure_contrast(spec.primary, bg, target=4.6)
    accent = ensure_contrast(spec.accent, bg, target=3.8)
    return {
        "PRIMARY": primary,
        "PRIMARY_LIGHT": mix(primary, _LIGHT_SURFACE, 0.18),
        "PRIMARY_DARK": mix(primary, "#000000", 0.16),
        "PRIMARY_BG": mix(_LIGHT_SURFACE, primary, 0.13),
        "ACCENT": accent,
        "ACCENT_LIGHT": mix(accent, _LIGHT_SURFACE, 0.18),
        "ON_PRIMARY": readable_on(primary),
        "ON_ACCENT": readable_on(accent),
        "BG": bg,
        "SURFACE": _LIGHT_SURFACE,
        "SURFACE_SOFT": mix(_LIGHT_SURFACE, primary, 0.085),
        "BORDER": mix(_LIGHT_SURFACE, primary, 0.17),
        "BORDER_FOCUS": mix(primary, _LIGHT_SURFACE, 0.35),
        "TEXT_MAIN": mix(_TEXT_INK, primary, 0.07),
        "TEXT_DIM": mix("#475569", primary, 0.07),
        "TEXT_MUTED": mix(_MUTED_INK, primary, 0.06),
        "SCAFFOLD": bg,
        "CANVAS": bg,
        "CARD": _LIGHT_SURFACE,
        # 悬浮卡是「深色质感卡片」，与主题同色相，任何配色下都能压住底层内容
        "TOOLTIP_BG": mix("#121a26", primary, 0.14),
        "TOOLTIP_TEXT": "#f6f9fd",
        "ERROR": _ERROR_LIGHT,
        "ON_ERROR": readable_on(_ERROR_LIGHT),
    }


def _dark(spec: ThemeSpec) -> Tokens:
    primary = spec.dark_primary or mix(spec.primary, _LIGHT_SURFACE, 0.34)
    accent = spec.dark_accent or mix(spec.accent, _LIGHT_SURFACE, 0.30)
    base = spec.dark_base or _DARK_BASE
    bg = mix(base, primary, spec.tint * 0.9)
    return {
        "PRIMARY": primary,
        "PRIMARY_LIGHT": mix(primary, _LIGHT_SURFACE, 0.20),
        "PRIMARY_DARK": mix(primary, "#000000", 0.22),
        "PRIMARY_BG": mix(bg, primary, 0.20),
        "ACCENT": accent,
        "ACCENT_LIGHT": mix(accent, _LIGHT_SURFACE, 0.18),
        "ON_PRIMARY": readable_on(primary),
        "ON_ACCENT": readable_on(accent),
        "BG": bg,
        "SURFACE": mix(bg, _LIGHT_SURFACE, 0.055),
        "SURFACE_SOFT": mix(bg, _LIGHT_SURFACE, 0.11),
        "BORDER": mix(bg, _LIGHT_SURFACE, 0.16),
        "BORDER_FOCUS": primary,
        "TEXT_MAIN": mix("#f4f7fb", primary, 0.04),
        "TEXT_DIM": mix("#c3cedb", primary, 0.05),
        "TEXT_MUTED": mix("#8a99ac", primary, 0.05),
        "SCAFFOLD": bg,
        "CANVAS": bg,
        "CARD": mix(bg, _LIGHT_SURFACE, 0.055),
        # 深色下「卡片比背景亮一档」才看得出边界，所以反色卡也跟着换向
        "TOOLTIP_BG": mix(bg, _LIGHT_SURFACE, 0.10),
        "TOOLTIP_TEXT": "#f4f7fb",
        "ERROR": _ERROR_DARK,
        "ON_ERROR": readable_on(_ERROR_DARK),
    }


def build_palette(theme: ColorTheme, *, dark: bool) -> Tokens:
    """推导某个配色在指定明暗下的完整令牌表。

    Args:
        theme: 配色标识。
        dark: ``True`` 取深色版。

    Returns:
        令牌名 → ``#rrggbb``。键集合恒为 :data:`PALETTE_KEYS`。
    """
    return _dark(spec_of(theme)) if dark else _light(spec_of(theme))


# 早绑定校验：配色与声明表必须一一对应，否则选择面板会缺项（导入期就炸，
# 比运行到一半才发现好）。
_MISSING = [theme for theme in COLOR_THEMES if theme not in THEME_SPECS]
if _MISSING:  # pragma: no cover - 声明表写漏了才会走到
    raise RuntimeError(f"缺少配色声明：{_MISSING}")
