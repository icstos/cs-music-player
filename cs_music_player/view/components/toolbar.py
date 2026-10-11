"""工具栏：桌面歌词入口与睡眠定时器入口。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ..theme import palette
from .format import fmt_duration

__all__ = ["DesktopLyricButton", "SleepTimerButton"]


# ── 桌面歌词入口 ── #


@ft.component
def DesktopLyricButton(
    enabled: bool,
    locked: bool,
    font_size: float,
    on_toggle: Callable[[], None],
    on_toggle_lock: Callable[[], None],
    on_font_step: Callable[[float], None],
    on_reset_font: Callable[[], None],
    on_close: Callable[[], None],
) -> ft.Control:
    """工具栏上的桌面歌词入口。

    开关、锁定、字号都收在一个菜单里：桌面歌词的浮窗本身就是「无边框、可穿透」
    的，主界面必须留一条随时能把它收回来 / 解锁的路——否则锁定后用户就再也点
    不到它了。
    """
    active = enabled

    def item(
        icon: ft.IconData,
        label: str,
        on_click: Callable[[], None],
        *,
        accent: bool = False,
        hint: str = "",
    ) -> ft.PopupMenuItem:
        return ft.PopupMenuItem(
            content=ft.Row(
                [
                    ft.Icon(
                        icon,
                        size=16,
                        color=palette.ACCENT if accent else palette.TEXT_DIM,
                    ),
                    ft.Text(label, size=12, color=palette.TEXT_MAIN),
                    ft.Container(expand=True),
                    ft.Text(hint, size=11, color=palette.TEXT_MUTED)
                    if hint
                    else ft.Container(),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e: on_click(),
        )

    def divider() -> ft.PopupMenuItem:
        return ft.PopupMenuItem(
            content=ft.Divider(height=1, color=palette.BORDER), height=1
        )

    items: list[ft.PopupMenuItem] = [
        item(
            ft.Icons.CLOSE if enabled else ft.Icons.SUBTITLES,
            "隐藏桌面歌词" if enabled else "显示桌面歌词",
            on_toggle,
            accent=enabled,
            hint="已开启" if enabled else "已关闭",
        )
    ]
    if enabled:
        items.append(
            item(
                ft.Icons.LOCK if locked else ft.Icons.LOCK_OPEN,
                "解锁歌词（可拖动、可操作）" if locked else "锁定歌词（鼠标穿透）",
                on_toggle_lock,
                accent=locked,
                hint="鼠标穿透中" if locked else "",
            )
        )
        items.append(divider())
        items.append(
            item(
                ft.Icons.TEXT_INCREASE,
                "增大歌词字体",
                lambda: on_font_step(1.0),
                hint=f"{font_size:g}",
            )
        )
        items.append(
            item(ft.Icons.TEXT_DECREASE, "减小歌词字体", lambda: on_font_step(-1.0))
        )
        items.append(
            item(ft.Icons.RESTART_ALT, "恢复默认字体", on_reset_font)
        )
        items.append(divider())
        items.append(item(ft.Icons.POWER_SETTINGS_NEW, "关闭桌面歌词", on_close))

    tooltip = "桌面歌词"
    if enabled:
        tooltip = "桌面歌词（已开启" + ("，已锁定" if locked else "") + "）"

    return ft.PopupMenuButton(
        icon=ft.Icons.SUBTITLES if not active else ft.Icons.SUBTITLES_ROUNDED,
        icon_color=palette.PRIMARY_DARK if active else palette.TEXT_DIM,
        icon_size=22,
        tooltip=tooltip,
        style=ft.ButtonStyle(padding=ft.Padding.all(8)),
        menu_position=ft.PopupMenuPosition.UNDER,
        size_constraints=ft.BoxConstraints(min_width=248, max_width=248),
        items=items,
    )


@ft.component
def SleepTimerButton(
    remaining: float,
    on_click: Callable[[], None],
) -> ft.Control:
    """睡眠定时器入口：仅图标，激活时强调色提示。"""
    active = remaining > 0
    tooltip = (
        f"睡眠定时器（剩余 {fmt_duration(remaining)}）"
        if active
        else "睡眠定时器"
    )
    return ft.IconButton(
        icon=ft.Icons.BEDTIME if active else ft.Icons.BEDTIME_OUTLINED,
        icon_color=palette.ACCENT if active else palette.TEXT_DIM,
        icon_size=20,
        tooltip=tooltip,
        on_click=lambda e: on_click(),
        style=ft.ButtonStyle(
            padding=ft.Padding.all(8),
            overlay_color=ft.Colors.with_opacity(0.08, palette.PRIMARY),
        ),
    )
