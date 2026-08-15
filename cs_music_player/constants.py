"""共享常量：文件格式、播放模式、主题调色板、图标映射。

主题配色通过 :data:`palette` 动态访问——组件在渲染时读取当前
激活调色板，因此亮/暗主题可在运行期切换。
"""

from __future__ import annotations

import flet as ft

# ── 文件格式 ── #
SUPPORTED_FORMATS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
SUPPORTED_LYRICS_FORMATS = (".lrc", ".txt")

# ── 播放模式 ── #
MODE_SEQUENCE = "顺序播放"
MODE_LOOP_ONE = "单曲循环"
MODE_SHUFFLE = "随机播放"
MODE_ORDER = (MODE_SEQUENCE, MODE_LOOP_ONE, MODE_SHUFFLE)
MODE_ICONS = {
    MODE_SEQUENCE: ft.Icons.REPEAT,
    MODE_LOOP_ONE: ft.Icons.REPEAT_ONE,
    MODE_SHUFFLE: ft.Icons.SHUFFLE,
}

# ── 调色板（亮 / 暗两套，键名保持一致）── #
_LIGHT_PALETTE = {
    "PRIMARY": "#2563eb",
    "PRIMARY_LIGHT": "#3b82f6",
    "PRIMARY_DARK": "#1d4ed8",
    "ACCENT": "#7c3aed",
    "ACCENT_LIGHT": "#8b5cf6",
    "BG": "#f5f7fb",
    "SURFACE": "#ffffff",
    "SURFACE_SOFT": "#eef2f7",
    "PRIMARY_BG": "#eff6ff",
    "BORDER": "#dbe3ee",
    "BORDER_FOCUS": "#93c5fd",
    "TEXT_MAIN": "#0f172a",
    "TEXT_DIM": "#475569",
    "TEXT_MUTED": "#94a3b8",
    "SCAFFOLD": "#f5f7fb",
    "CANVAS": "#f5f7fb",
    "CARD": "#ffffff",
}

_DARK_PALETTE = {
    "PRIMARY": "#60a5fa",
    "PRIMARY_LIGHT": "#93c5fd",
    "PRIMARY_DARK": "#3b82f6",
    "ACCENT": "#a78bfa",
    "ACCENT_LIGHT": "#c4b5fd",
    "BG": "#0b1220",
    "SURFACE": "#111827",
    "SURFACE_SOFT": "#1e293b",
    "PRIMARY_BG": "#172554",
    "BORDER": "#243244",
    "BORDER_FOCUS": "#60a5fa",
    "TEXT_MAIN": "#f1f5f9",
    "TEXT_DIM": "#cbd5e1",
    "TEXT_MUTED": "#94a3b8",
    "SCAFFOLD": "#0b1220",
    "CANVAS": "#0b1220",
    "CARD": "#111827",
}

THEME_MODES = ("light", "dark", "system")


class _Palette:
    """按名字从当前激活调色板读取颜色值。"""

    def __init__(self) -> None:
        object.__setattr__(self, "_active", _LIGHT_PALETTE)

    def set_mode(self, mode: str) -> None:
        object.__setattr__(
            self,
            "_active",
            _DARK_PALETTE if mode == "dark" else _LIGHT_PALETTE,
        )

    def __getattr__(self, name: str) -> str:
        try:
            return object.__getattribute__(self, "_active")[name]
        except KeyError:
            raise AttributeError(name) from None

    # —— 派生透明色：跟随当前主色/强调色动态生成 —— #
    @property
    def PRIMARY_TINT_08(self) -> str:
        return ft.Colors.with_opacity(0.08, self.PRIMARY)

    @property
    def PRIMARY_TINT_12(self) -> str:
        return ft.Colors.with_opacity(0.12, self.PRIMARY)

    @property
    def PRIMARY_TINT_16(self) -> str:
        return ft.Colors.with_opacity(0.16, self.PRIMARY)

    @property
    def ACCENT_TINT_10(self) -> str:
        return ft.Colors.with_opacity(0.10, self.ACCENT)

    def tint(self, base: str, opacity: float) -> str:
        return ft.Colors.with_opacity(opacity, getattr(self, base))


palette = _Palette()

THEME_SEED_LIGHT = _LIGHT_PALETTE["PRIMARY"]
THEME_SEED_DARK = _DARK_PALETTE["PRIMARY"]

# ── 本地字体 ── #
FONT_FAMILY = "Alibaba PuHuiTi"
FONT_FAMILY_FILE = "/fonts/AlibabaPuHuiTi-3-55-Regular.otf"


def build_light_theme() -> ft.Theme:
    """供 page.theme 使用：亮色 Material3 主题。"""
    return ft.Theme(
        color_scheme_seed=THEME_SEED_LIGHT,
        use_material3=True,
        font_family=FONT_FAMILY,
        scaffold_bgcolor=_LIGHT_PALETTE["SCAFFOLD"],
        canvas_color=_LIGHT_PALETTE["CANVAS"],
        card_bgcolor=_LIGHT_PALETTE["CARD"],
    )


def build_dark_theme() -> ft.Theme:
    """供 page.dark_theme 使用：暗色 Material3 主题。"""
    return ft.Theme(
        color_scheme_seed=THEME_SEED_DARK,
        use_material3=True,
        font_family=FONT_FAMILY,
        scaffold_bgcolor=_DARK_PALETTE["SCAFFOLD"],
        canvas_color=_DARK_PALETTE["CANVAS"],
        card_bgcolor=_DARK_PALETTE["CARD"],
    )