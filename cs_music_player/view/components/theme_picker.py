"""配色与外观选择器：工具栏入口 + 原生悬浮菜单。

交互约定（桌面直觉）：

- 点工具栏的调色板图标弹出菜单，点菜单外任何位置收起（原生行为，含 Esc）；
- 点配色即生效并持久化；点「外观」独立切换明暗——配色与明暗是正交维度；
- 选中带倾向的配色（极简白 / 暗夜黑）时，视图模型会顺手把外观切过去。

为什么用 ``PopupMenuButton`` 而不是自己拿 ``Stack`` 叠一层浮层：本项目用的
flet 1.0 里，``Stack`` 一旦出现在页面根上就会把所有指针事件吞掉（控件画得
出来、点哪儿都没反应）。PopupMenu 是 Flutter 原生浮层，锚定、阴影、避让
屏幕边缘、点外关闭、Esc 收起全都由框架负责，也不需要维护"面板是否打开"
这个视图状态。
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ...models import (
    THEME_PREFERRED_MODE,
    ColorTheme,
    ThemeMode,
)
from ..colors import build_palette, spec_of
from ..theme import THEME_ICONS, THEME_LABELS, palette, theme_label

__all__ = ["ThemeMenuButton", "build_theme_menu"]

#: 菜单内容尺寸（逻辑像素）。高度按内容逐行算好，PopupMenuItem 会照此定高。
PANEL_WIDTH = 336
_MENU_HEIGHT = 348
_CHIP_WIDTH = 152
_CHIP_HEIGHT = 36


# ── 面板内的小控件 ── #


def _swatch(theme: ColorTheme) -> ft.Control:
    """配色样本：外圈主色、内芯是该配色自己的底色。

    内芯取「该配色自己的底色」，而不是当前底色——这样在深色界面里看极简白，
    显示的仍是它本来的样子。最外面再加一道当前描边：否则深色界面下深色的
    外圈（极简白、暗夜黑）会与面板背景融成一片，看不出圆点。
    """
    prefers_dark = THEME_PREFERRED_MODE.get(theme) == ThemeMode.DARK
    tokens = build_palette(theme, dark=prefers_dark)
    return ft.Container(
        width=20,
        height=20,
        border_radius=10,
        alignment=ft.Alignment.CENTER,
        border=ft.Border.all(1, palette.BORDER),
        content=ft.Container(
            width=16,
            height=16,
            border_radius=8,
            bgcolor=tokens["SURFACE"],
            # 外圈取「该配色偏好明暗下的主色」：暗夜黑因此是浅圈深芯，
            # 与极简白（深圈白芯）在样本尺度上也不会看混
            border=ft.Border.all(4, tokens["PRIMARY"]),
        ),
    )


def _chip(
    theme: ColorTheme,
    is_active: bool,
    on_click: Callable[[ft.ControlEvent], None],
) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                _swatch(theme),
                ft.Text(
                    spec_of(theme).label,
                    size=12,
                    weight=ft.FontWeight.W_600
                    if is_active
                    else ft.FontWeight.NORMAL,
                    color=palette.TEXT_MAIN if is_active else palette.TEXT_DIM,
                    max_lines=1,
                ),
                ft.Container(expand=True),
                ft.Icon(
                    ft.Icons.CHECK_ROUNDED,
                    size=15,
                    color=palette.PRIMARY,
                    visible=is_active,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=_CHIP_WIDTH,
        height=_CHIP_HEIGHT,
        padding=ft.Padding.symmetric(horizontal=10),
        border_radius=10,
        ink=True,
        bgcolor=palette.PRIMARY_BG if is_active else None,
        border=ft.Border.all(1, palette.PRIMARY if is_active else palette.BORDER),
        on_click=on_click,
    )


def _mode_pill(
    mode: ThemeMode,
    is_active: bool,
    on_click: Callable[[ft.ControlEvent], None],
) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    THEME_ICONS[mode],
                    size=14,
                    color=palette.ON_PRIMARY if is_active else palette.TEXT_MUTED,
                ),
                ft.Text(
                    THEME_LABELS[mode],
                    size=11.5,
                    weight=ft.FontWeight.W_600
                    if is_active
                    else ft.FontWeight.NORMAL,
                    color=palette.ON_PRIMARY if is_active else palette.TEXT_DIM,
                ),
            ],
            spacing=5,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        expand=True,
        height=30,
        border_radius=8,
        ink=True,
        bgcolor=palette.PRIMARY if is_active else palette.SURFACE_SOFT,
        on_click=on_click,
    )


def _section_hint(icon: ft.IconData, text: str, hint: str) -> ft.Control:
    return ft.Row(
        [
            ft.Icon(icon, size=13, color=palette.TEXT_MUTED),
            ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=palette.TEXT_DIM),
            ft.Container(expand=True),
            ft.Text(hint, size=10, color=palette.TEXT_MUTED),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


# ── 菜单内容 ── #


def build_theme_menu(
    color: ColorTheme,
    mode: ThemeMode,
    on_pick_color: Callable[[ColorTheme], None],
    on_pick_mode: Callable[[ThemeMode], None],
) -> ft.PopupMenuItem:
    """整套配色 / 外观面板，作为悬浮菜单里唯一的一项。

    ``on_click`` 故意留空：Flet 只在条目自身有 on_click 时才在点击后关闭菜单，
    这样点色点可以连着试几套，菜单不会自己收起来。
    """
    return ft.PopupMenuItem(
        padding=ft.Padding.all(12),
        height=_MENU_HEIGHT,
        content=ft.Column(
            [
                _section_hint(ft.Icons.COLOR_LENS_OUTLINED, "配色主题", "点击即生效"),
                ft.Row(
                    [
                        _chip(theme, theme == color, lambda e, t=theme: on_pick_color(t))
                        for theme in ColorTheme
                    ],
                    wrap=True,
                    spacing=8,
                    run_spacing=8,
                ),
                ft.Divider(height=1, color=palette.BORDER),
                _section_hint(ft.Icons.BRIGHTNESS_6_OUTLINED, "外观", "可随时切换"),
                ft.Row(
                    [
                        _mode_pill(each, each == mode, lambda e, m=each: on_pick_mode(m))
                        for each in (
                            ThemeMode.LIGHT,
                            ThemeMode.DARK,
                            ThemeMode.SYSTEM,
                        )
                    ],
                    spacing=6,
                ),
            ],
            spacing=10,
            tight=True,
        ),
    )


# ── 工具栏入口 ── #


@ft.component
def ThemeMenuButton(
    color: ColorTheme,
    mode: ThemeMode,
    on_pick_color: Callable[[ColorTheme], None],
    on_pick_mode: Callable[[ThemeMode], None],
) -> ft.Control:
    """工具栏上的调色板入口；面板由原生菜单承载。"""
    return ft.PopupMenuButton(
        icon=ft.Icons.PALETTE_OUTLINED,
        icon_color=palette.TEXT_DIM,
        icon_size=22,
        tooltip=f"配色：{theme_label(color)}（点击更换）",
        style=ft.ButtonStyle(padding=ft.Padding.all(8)),
        menu_position=ft.PopupMenuPosition.UNDER,
        size_constraints=ft.BoxConstraints(
            min_width=PANEL_WIDTH + 24, max_width=PANEL_WIDTH + 24
        ),
        items=[build_theme_menu(color, mode, on_pick_color, on_pick_mode)],
    )
