"""配色与外观选择器：工具栏入口 + 原生悬浮菜单。

交互约定（桌面直觉）：

- 点工具栏的调色板图标弹出菜单，点菜单外任何位置收起（原生行为，含 Esc）；
- 点配色即生效并持久化；点「外观」独立切换明暗——配色与明暗是正交维度；
- 选中带倾向的配色（极简白 / 暗夜黑）时，视图模型会顺手把外观切过去。

为什么用 ``PopupMenuButton`` 而不是自己拿 ``Stack`` 叠一层浮层：本项目用的
flet 里，``Stack`` 一旦出现在页面根上就会把所有指针事件吞掉（控件画得出来、
点哪儿都没反应）。PopupMenu 是 Flutter 原生浮层，锚定、阴影、避让屏幕边缘、
点外关闭、Esc 收起全都由框架负责，也不需要维护"面板是否打开"这个视图状态。

样本色由 cs-ui 的色板引擎现算（``build_scheme``）：**样本展示的是它本来的
样子**，而不是当前配色下的色值——在深色界面里看「极简白」，看到的仍是白底
黑主色。计算量按配色缓存，菜单反复开合不会重复解算。
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from ui import (
    Alignment,
    Border,
    BoxConstraints,
    ButtonStyle,
    Colors,
    Column,
    Container,
    Control,
    ControlEvent,
    CrossAxisAlignment,
    Divider,
    FontWeight,
    Icon,
    IconData,
    Icons,
    MainAxisAlignment,
    Padding,
    PopupMenuButton,
    PopupMenuItem,
    PopupMenuPosition,
    Row,
    SPACE,
    Text,
    component,
    selected_layer,
)
from ui.core.palette import build_scheme

from ...models import (
    THEME_PREFERRED_MODE,
    ColorTheme,
    ThemeMode,
    seed_of,
)
from .. import tokens as t
from ..theme import THEME_ICONS, THEME_LABELS, theme_label

__all__ = ["ThemeMenuButton", "build_theme_menu"]

#: 菜单宽度：两列 152 的样本 + 两处 8px 间隙 + 左右 12 内边距。
PANEL_WIDTH = 336
_MENU_HEIGHT = 344
_CHIP_WIDTH = 152
_CHIP_HEIGHT = 36


@lru_cache(maxsize=32)
def _swatch_colors(theme: ColorTheme) -> tuple[str, str]:
    """样本色 ``(底色, 主色)``：取该配色**偏好明暗**下的一套，反映它的本色。"""
    prefers_dark = THEME_PREFERRED_MODE.get(theme) == ThemeMode.DARK
    scheme = build_scheme(seed_of(theme), "dark" if prefers_dark else "light")
    return scheme["surface"], scheme["primary"]


# ── 面板内的小控件 ── #


def _swatch(theme: ColorTheme) -> Control:
    """配色样本：外圈主色、内芯是该配色自己的底色。

    内芯取「该配色自己的底色」，而不是当前底色——这样在深色界面里看极简白，
    显示的仍是它本来的样子。最外面再加一道当前描边：否则深色界面下深色的
    外圈（极简白、暗夜黑）会与面板背景融成一片，看不出圆点。
    """
    surface, primary = _swatch_colors(theme)
    return Container(
        width=20,
        height=20,
        border_radius=10,
        alignment=Alignment.CENTER,
        border=Border.all(1, t.LINE),
        content=Container(
            width=16,
            height=16,
            border_radius=8,
            bgcolor=surface,
            # 外圈取「该配色偏好明暗下的主色」：暗夜黑因此是浅圈深芯，
            # 与极简白（深圈白芯）在样本尺度上也不会看混
            border=Border.all(4, primary),
        ),
    )


def _chip(
    theme: ColorTheme,
    is_active: bool,
    on_click: Callable[[ControlEvent], None],
) -> Control:
    return Container(
        content=Row(
            controls=[
                _swatch(theme),
                Text(
                    theme_label(theme),
                    size=12,
                    weight=FontWeight.W_600
                    if is_active
                    else FontWeight.NORMAL,
                    color=t.TEXT if is_active else t.TEXT_SOFT,
                    max_lines=1,
                ),
                Container(expand=True),
                Icon(
                    Icons.CHECK_ROUNDED,
                    size=15,
                    color=Colors.PRIMARY,
                    visible=is_active,
                ),
            ],
            spacing=SPACE["2"],
            vertical_alignment=CrossAxisAlignment.CENTER,
        ),
        width=_CHIP_WIDTH,
        height=_CHIP_HEIGHT,
        padding=Padding.symmetric(horizontal=SPACE["2"]),
        border_radius=10,
        ink=True,
        bgcolor=selected_layer("normal") if is_active else None,
        border=Border.all(1, Colors.PRIMARY if is_active else t.LINE),
        on_click=on_click,
    )


def _mode_pill(
    mode: ThemeMode,
    is_active: bool,
    on_click: Callable[[ControlEvent], None],
) -> Control:
    return Container(
        content=Row(
            controls=[
                Icon(
                    THEME_ICONS[mode],
                    size=14,
                    color=Colors.ON_PRIMARY if is_active else t.TEXT_SOFT,
                ),
                Text(
                    THEME_LABELS[mode],
                    size=11,
                    weight=FontWeight.W_600
                    if is_active
                    else FontWeight.NORMAL,
                    color=Colors.ON_PRIMARY if is_active else t.TEXT_SOFT,
                ),
            ],
            spacing=5,
            alignment=MainAxisAlignment.CENTER,
            vertical_alignment=CrossAxisAlignment.CENTER,
        ),
        expand=True,
        height=32,
        border_radius=8,
        ink=True,
        bgcolor=Colors.PRIMARY if is_active else t.PANEL_HIGH,
        on_click=on_click,
    )


def _section_hint(icon: IconData, text: str, hint: str) -> Control:
    return Row(
        controls=[
            Icon(icon, size=13, color=t.TEXT_SOFT),
            Text(text, size=11, weight=FontWeight.W_600, color=t.TEXT),
            Container(expand=True),
            Text(hint, size=10, color=t.TEXT_SOFT),
        ],
        spacing=6,
        vertical_alignment=CrossAxisAlignment.CENTER,
    )


# ── 菜单内容 ── #


def build_theme_menu(
    color: ColorTheme,
    mode: ThemeMode,
    on_pick_color: Callable[[ColorTheme], None],
    on_pick_mode: Callable[[ThemeMode], None],
) -> PopupMenuItem:
    """整套配色 / 外观面板，作为悬浮菜单里唯一的一项。

    ``on_click`` 故意留空：Flet 只在条目自身有 on_click 时才在点击后关闭菜单，
    这样点色点可以连着试几套，菜单不会自己收起来。
    """
    return PopupMenuItem(
        padding=Padding.all(SPACE["3"]),
        height=_MENU_HEIGHT,
        content=Column(
            controls=[
                _section_hint(Icons.COLOR_LENS_OUTLINED, "配色主题", "点击即生效"),
                Row(
                    controls=[
                        _chip(theme, theme == color, lambda e, c=theme: on_pick_color(c))
                        for theme in ColorTheme
                    ],
                    wrap=True,
                    spacing=SPACE["2"],
                    run_spacing=SPACE["2"],
                ),
                Divider(height=1, color=t.LINE),
                _section_hint(Icons.BRIGHTNESS_6_OUTLINED, "外观", "与配色无关"),
                Row(
                    controls=[
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
            spacing=SPACE["2"],
            tight=True,
        ),
    )


# ── 工具栏入口 ── #


@component
def ThemeMenuButton(
    color: ColorTheme,
    mode: ThemeMode,
    on_pick_color: Callable[[ColorTheme], None],
    on_pick_mode: Callable[[ThemeMode], None],
) -> Control:
    """工具栏上的调色板入口；面板由原生菜单承载。

    图标颜色跟着当前品牌色走 —— 它本身就是「主色现在是什么」的指示器。
    """
    label = theme_label(color)
    return PopupMenuButton(
        icon=Icons.PALETTE_OUTLINED,
        icon_color=Colors.PRIMARY,
        icon_size=22,
        tooltip=f"配色：{label}（点击更换）",
        style=ButtonStyle(padding=Padding.all(8)),
        menu_position=PopupMenuPosition.UNDER,
        size_constraints=BoxConstraints(
            min_width=PANEL_WIDTH + 24, max_width=PANEL_WIDTH + 24
        ),
        items=[build_theme_menu(color, mode, on_pick_color, on_pick_mode)],
    )
