"""视图层的主题系统：调色板、Flet 主题对象、图标映射。

``palette`` 是一个**全局可切换的调色板代理**：组件在渲染时读取
``palette.PRIMARY`` 之类的属性，因此亮 / 暗主题可以在运行期原子切换。
切换发生在根组件渲染之前（见 :func:`cs_music_player.view.app.PlayerApp`），
所以同一次渲染里所有组件读到的都是同一套颜色。
"""

from __future__ import annotations

import flet as ft

from ..models import (
    DARK_PALETTE,
    FONT_FAMILY,
    LIGHT_PALETTE,
    PlayMode,
    ThemeMode,
)

__all__ = [
    "MODE_ICONS",
    "THEME_ICONS",
    "THEME_LABELS",
    "Palette",
    "build_dark_theme",
    "build_light_theme",
    "palette",
]

#: 播放模式 → 图标。
MODE_ICONS: dict[PlayMode, ft.IconData] = {
    PlayMode.SEQUENCE: ft.Icons.REPEAT,
    PlayMode.LOOP_ONE: ft.Icons.REPEAT_ONE,
    PlayMode.SHUFFLE: ft.Icons.SHUFFLE,
}

#: 主题模式 → 图标 / 悬浮说明。
THEME_ICONS: dict[ThemeMode, ft.IconData] = {
    ThemeMode.LIGHT: ft.Icons.LIGHT_MODE,
    ThemeMode.DARK: ft.Icons.DARK_MODE,
    ThemeMode.SYSTEM: ft.Icons.BRIGHTNESS_AUTO,
}
THEME_LABELS: dict[ThemeMode, str] = {
    ThemeMode.LIGHT: "浅色主题",
    ThemeMode.DARK: "深色主题",
    ThemeMode.SYSTEM: "跟随系统",
}

THEME_SEED_LIGHT: str = LIGHT_PALETTE["PRIMARY"]
THEME_SEED_DARK: str = DARK_PALETTE["PRIMARY"]


class Palette:
    """按名字从当前激活的调色板读取颜色值。

    用 ``__getattr__`` 代理而不是把颜色复制成属性：切换主题只需换掉
    ``_active`` 这张表，所有组件下次渲染就拿到新颜色。
    """

    def __init__(self) -> None:
        object.__setattr__(self, "_active", LIGHT_PALETTE)

    @property
    def active(self) -> dict[str, str]:
        """当前激活的调色板。"""
        return object.__getattribute__(self, "_active")

    def set_mode(self, mode: str) -> None:
        """按 ``"light"`` / ``"dark"`` 切换调色板。"""
        object.__setattr__(
            self,
            "_active",
            DARK_PALETTE if mode == ThemeMode.DARK else LIGHT_PALETTE,
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


palette = Palette()


def build_light_theme() -> ft.Theme:
    """供 ``page.theme`` 使用：亮色 Material3 主题。"""
    return ft.Theme(
        color_scheme_seed=THEME_SEED_LIGHT,
        use_material3=True,
        font_family=FONT_FAMILY,
        scaffold_bgcolor=LIGHT_PALETTE["SCAFFOLD"],
        canvas_color=LIGHT_PALETTE["CANVAS"],
        card_bgcolor=LIGHT_PALETTE["CARD"],
    )


def build_dark_theme() -> ft.Theme:
    """供 ``page.dark_theme`` 使用：暗色 Material3 主题。"""
    return ft.Theme(
        color_scheme_seed=THEME_SEED_DARK,
        use_material3=True,
        font_family=FONT_FAMILY,
        scaffold_bgcolor=DARK_PALETTE["SCAFFOLD"],
        canvas_color=DARK_PALETTE["CANVAS"],
        card_bgcolor=DARK_PALETTE["CARD"],
    )
