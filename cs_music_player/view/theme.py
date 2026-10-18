"""视图层的主题系统：调色板代理、Flet 主题对象、图标映射。

``palette`` 是一个**全局可切换的调色板代理**：组件在渲染时读取
``palette.PRIMARY`` 之类的属性，因此「配色 + 明暗」可以在运行期原子切换。
切换发生在根组件渲染之前（见 :func:`cs_music_player.view.app.PlayerApp`），
所以同一次渲染里所有组件读到的都是同一套颜色。

具体色值由 :mod:`cs_music_player.view.colors` 从「主色 + 强调色」推导；
本模块只负责把令牌表包成代理、并翻译成 Flet 的 ``Theme`` 对象。
"""

from __future__ import annotations

from functools import lru_cache

import flet as ft

from ..models import (
    DEFAULT_COLOR_THEME,
    FONT_FAMILY,
    ColorTheme,
    PlayMode,
    ThemeMode,
)
from .colors import Tokens, build_palette, spec_of

__all__ = [
    "MODE_ICONS",
    "THEME_ICONS",
    "THEME_LABELS",
    "Palette",
    "apply_palette",
    "build_dark_theme",
    "build_light_theme",
    "palette",
    "sync_page_theme",
    "theme_label",
]

#: 播放模式 → 图标。
MODE_ICONS: dict[PlayMode, ft.IconData] = {
    PlayMode.SEQUENCE: ft.Icons.REPEAT,
    PlayMode.LOOP_ONE: ft.Icons.REPEAT_ONE,
    PlayMode.SHUFFLE: ft.Icons.SHUFFLE,
}

#: 明暗模式 → 图标 / 文案。
THEME_ICONS: dict[ThemeMode, ft.IconData] = {
    ThemeMode.LIGHT: ft.Icons.LIGHT_MODE,
    ThemeMode.DARK: ft.Icons.DARK_MODE,
    ThemeMode.SYSTEM: ft.Icons.BRIGHTNESS_AUTO,
}
THEME_LABELS: dict[ThemeMode, str] = {
    ThemeMode.LIGHT: "浅色",
    ThemeMode.DARK: "深色",
    ThemeMode.SYSTEM: "跟随",
}


class Palette:
    """按名字从当前激活的调色板读取颜色值。

    用 ``__getattr__`` 代理而不是把颜色复制成属性：切换配色只需换掉
    ``_tokens`` 这张表，所有组件下次渲染就拿到新颜色。

    :meth:`use` 相同组合会**直接返回**，所以「每次渲染都调一次」不会重复推导。
    """

    def __init__(self) -> None:
        self._theme: ColorTheme = DEFAULT_COLOR_THEME
        self._dark: bool = False
        self._tokens: Tokens = build_palette(DEFAULT_COLOR_THEME, dark=False)

    @property
    def theme(self) -> ColorTheme:
        """当前配色。"""
        return self._theme

    @property
    def is_dark(self) -> bool:
        """当前是否为深色底。"""
        return self._dark

    @property
    def tokens(self) -> Tokens:
        """当前激活的整套令牌（只读用途，别就地改）。"""
        return self._tokens

    def use(self, theme: ColorTheme, *, dark: bool) -> bool:
        """切换到指定配色 / 明暗。

        Returns:
            是否真的切换了（供调用方判断要不要重推页面属性）。
        """
        if theme == self._theme and dark == self._dark:
            return False
        self._theme = theme
        self._dark = dark
        self._tokens = build_palette(theme, dark=dark)
        return True

    def __getattr__(self, name: str) -> str:
        try:
            return self._tokens[name]
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


def theme_label(theme: ColorTheme) -> str:
    """配色的显示名。"""
    return spec_of(theme).label


@lru_cache(maxsize=32)
def _scheme(theme: ColorTheme, dark: bool) -> ft.ColorScheme:
    """把令牌表映射成 Material 颜色方案。

    只给 ``color_scheme_seed`` 时，Material 会自己从种子色推一套调和色（按钮
    文字用「种子色算出来的 onPrimary」），结果和我们推导的调色板对不上——例如
    橙色按钮会拿到接近白色的文字，而不是我们按对比度选出来的深色墨水。
    显式给出方案后，Material 控件（按钮、Chip、输入框、弹窗、菜单）与本项目
    的配色完全同源。
    """
    tokens = build_palette(theme, dark=dark)
    return ft.ColorScheme(
        primary=tokens["PRIMARY"],
        on_primary=tokens["ON_PRIMARY"],
        primary_container=tokens["PRIMARY_BG"],
        on_primary_container=tokens["TEXT_MAIN"],
        secondary=tokens["ACCENT"],
        on_secondary=tokens["ON_ACCENT"],
        secondary_container=tokens["PRIMARY_BG"],
        on_secondary_container=tokens["TEXT_MAIN"],
        tertiary=tokens["ACCENT"],
        on_tertiary=tokens["ON_ACCENT"],
        error=tokens["ERROR"],
        on_error=tokens["ON_ERROR"],
        surface=tokens["SURFACE"],
        on_surface=tokens["TEXT_MAIN"],
        on_surface_variant=tokens["TEXT_DIM"],
        surface_container=tokens["SURFACE_SOFT"],
        surface_container_low=tokens["SURFACE"],
        surface_container_lowest=tokens["SURFACE"],
        surface_container_high=tokens["SURFACE_SOFT"],
        surface_container_highest=tokens["SURFACE_SOFT"],
        surface_bright=tokens["SURFACE"],
        surface_dim=tokens["BG"],
        outline=tokens["BORDER"],
        outline_variant=tokens["BORDER_FOCUS"],
        shadow=tokens["TEXT_MAIN"],
        scrim=tokens["TEXT_MAIN"],
        inverse_surface=tokens["TOOLTIP_BG"],
        on_inverse_surface=tokens["TOOLTIP_TEXT"],
        inverse_primary=tokens["PRIMARY_LIGHT"],
    )


@lru_cache(maxsize=32)
def _theme_for(theme: ColorTheme, dark: bool) -> ft.Theme:
    """把令牌表翻译成 Flet 主题（按「配色 + 明暗」缓存）。

    首次构造 ``ft.Theme`` 要付一次 flet 惰性导入的钱，缓存后换主题只是
    换个对象引用，不会反复付。
    """
    tokens = build_palette(theme, dark=dark)
    return ft.Theme(
        color_scheme_seed=tokens["PRIMARY"],
        color_scheme=_scheme(theme, dark),
        use_material3=True,
        font_family=FONT_FAMILY,
        scaffold_bgcolor=tokens["SCAFFOLD"],
        canvas_color=tokens["CANVAS"],
        card_bgcolor=tokens["CARD"],
        divider_color=tokens["BORDER"],
        hint_color=tokens["TEXT_MUTED"],
        # Material 控件（弹窗、菜单、Chip、提示条）跟随配色，避免主题是
        # 薰衣草紫、弹窗却是 Material 默认白灰的割裂感。
        primary_text_theme=ft.TextTheme(
            body_large=ft.TextStyle(size=14, color=tokens["TEXT_MAIN"]),
            body_medium=ft.TextStyle(size=13, color=tokens["TEXT_MAIN"]),
            body_small=ft.TextStyle(size=12, color=tokens["TEXT_DIM"]),
            label_large=ft.TextStyle(size=13, color=tokens["TEXT_MAIN"]),
            label_medium=ft.TextStyle(size=12, color=tokens["TEXT_DIM"]),
            title_medium=ft.TextStyle(
                size=16,
                weight=ft.FontWeight.W_700,
                color=tokens["TEXT_MAIN"],
            ),
        ),
        icon_theme=ft.IconTheme(color=tokens["TEXT_DIM"]),
        popup_menu_theme=ft.PopupMenuTheme(
            color=tokens["SURFACE"],
            label_text_style=ft.TextStyle(size=12, color=tokens["TEXT_MAIN"]),
            icon_color=tokens["TEXT_DIM"],
            shape=ft.RoundedRectangleBorder(radius=12),
            elevation=10,
        ),
        dialog_theme=ft.DialogTheme(
            bgcolor=tokens["SURFACE"],
            shape=ft.RoundedRectangleBorder(radius=16),
            title_text_style=ft.TextStyle(
                size=16,
                weight=ft.FontWeight.W_700,
                color=tokens["TEXT_MAIN"],
            ),
            content_text_style=ft.TextStyle(size=13, color=tokens["TEXT_DIM"]),
        ),
        chip_theme=ft.ChipTheme(
            # 未选中：白底细描边；选中：主色淡底 —— 两者必须在缩略图尺度上可分
            color=tokens["SURFACE"],
            bgcolor=tokens["SURFACE"],
            selected_color=tokens["PRIMARY_BG"],
            check_color=tokens["PRIMARY"],
            label_text_style=ft.TextStyle(size=12, color=tokens["TEXT_MAIN"]),
            border_side=ft.BorderSide(1, tokens["BORDER"]),
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        snackbar_theme=ft.SnackBarTheme(
            bgcolor=tokens["SURFACE"],
            content_text_style=ft.TextStyle(size=13, color=tokens["TEXT_MAIN"]),
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_color=tokens["BORDER"],
            track_color=ft.Colors.TRANSPARENT,
        ),
        # 提示条默认走 Material 的「反色面」，在深色主题下会变成白底黑字，
        # 与界面割裂；统一成本项目自己的提示卡配色（深底浅字，浅色主题亦然）。
        tooltip_theme=ft.TooltipTheme(
            text_style=ft.TextStyle(size=12, color=tokens["TOOLTIP_TEXT"]),
            decoration=ft.BoxDecoration(
                bgcolor=tokens["TOOLTIP_BG"],
                border_radius=8,
            ),
        ),
    )


def build_light_theme(color: ColorTheme = DEFAULT_COLOR_THEME) -> ft.Theme:
    """供 ``page.theme`` 使用：该配色的浅色 Material3 主题。"""
    return _theme_for(color, False)


def build_dark_theme(color: ColorTheme = DEFAULT_COLOR_THEME) -> ft.Theme:
    """供 ``page.dark_theme`` 使用：该配色的深色 Material3 主题。"""
    return _theme_for(color, True)


def apply_palette(color: ColorTheme, mode: str | ThemeMode) -> None:
    """把「配色 + 明暗」切到全局调色板。

    必须在**构造控件之前**调用——组件渲染时读 ``palette.*``，先换表后渲染，
    同一次渲染里所有组件拿到的才是同一套颜色。
    """
    palette.use(color, dark=str(mode) == ThemeMode.DARK)


def sync_page_theme(
    page: ft.Page, color: ColorTheme, mode: str | ThemeMode
) -> None:
    """把主题写到页面级属性上（明暗、导入主题、背景色）。

    组件模式下属性赋值不会自动下发，调用方负责随后的 ``page.update()``。
    """
    palette.use(color, dark=str(mode) == ThemeMode.DARK)
    page.theme_mode = (
        ft.ThemeMode.DARK if palette.is_dark else ft.ThemeMode.LIGHT
    )
    page.theme = build_light_theme(color)
    page.dark_theme = build_dark_theme(color)
    page.bgcolor = palette.BG
