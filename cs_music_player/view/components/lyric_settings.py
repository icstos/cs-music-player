"""歌词同步（偏移）与字号设置入口。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ...models import (
    LYRIC_FONT_DEFAULT,
    LYRIC_OFFSET_STEP_COARSE,
    LYRIC_OFFSET_STEP_FINE,
)
from ..theme import palette

__all__ = ["LyricSettingsEntry"]


# ── 歌词同步（隐藏式微调） ── #


def _offset_label(offset: float) -> str:
    """偏移秒数 → 可读文案（正值=提前，负值=延后）。"""
    if offset == 0:
        return "同步"
    direction = "提前" if offset > 0 else "延后"
    return f"{direction} {abs(round(offset, 3)):g}s"


@ft.component
def LyricSettingsEntry(
    offset: float,
    font_size: float,
    track_path: str,
    on_adjust: Callable[[float], None],
    on_adjust_font: Callable[[float], None],
) -> ft.Control:
    """歌词区右上角两个独立入口：歌词同步 与 字体大小。

    各为一个小图标，点击展开各自面板（互斥展开），切歌自动收起。
    """
    active, set_active = ft.use_state("")
    # 切歌时自动收起
    ft.use_effect(lambda: set_active(""), [track_path])

    sync_adjusted = offset != 0
    font_changed = abs(font_size - LYRIC_FONT_DEFAULT) > 1e-9
    sync_active = active == "sync"
    font_active = active == "font"

    def pill_button(
        text: str, tooltip: str, on_click: Callable[[ft.ControlEvent], None]
    ) -> ft.Control:
        return ft.Container(
            content=ft.Text(
                text,
                size=11,
                weight=ft.FontWeight.W_600,
                color=palette.PRIMARY,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=palette.PRIMARY_TINT_12,
            ink=True,
            tooltip=tooltip,
            on_click=on_click,
        )

    def reset_button(
        tooltip: str, on_click: Callable[[ft.ControlEvent], None]
    ) -> ft.Control:
        return ft.Container(
            content=ft.Icon(ft.Icons.REFRESH, size=15, color=palette.TEXT_DIM),
            padding=ft.Padding.all(5),
            border_radius=8,
            ink=True,
            tooltip=tooltip,
            on_click=on_click,
        )

    def toggle_chip(
        icon: ft.IconData,
        label: str,
        is_active: bool,
        is_changed: bool,
        tooltip: str,
        on_click: Callable[[ft.ControlEvent], None],
    ) -> ft.Control:
        highlighted = is_active or is_changed
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        icon,
                        size=16,
                        color=palette.ACCENT if highlighted else palette.TEXT_MUTED,
                    ),
                    ft.Text(
                        label,
                        size=11,
                        weight=ft.FontWeight.W_600
                        if highlighted
                        else ft.FontWeight.NORMAL,
                        color=palette.ACCENT if highlighted else palette.TEXT_MUTED,
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=14,
            bgcolor=palette.ACCENT_TINT_10 if highlighted else ft.Colors.TRANSPARENT,
            ink=True,
            tooltip=tooltip,
            on_click=on_click,
        )

    sync_toggle = toggle_chip(
        ft.Icons.TUNE,
        _offset_label(offset),
        sync_active,
        sync_adjusted,
        "歌词同步调整",
        lambda e: set_active("sync" if not sync_active else ""),
    )
    font_toggle = toggle_chip(
        ft.Icons.FORMAT_SIZE,
        f"{font_size:g}px",
        font_active,
        font_changed,
        "歌词字体大小",
        lambda e: set_active("font" if not font_active else ""),
    )

    sync_bar = ft.Container(
        content=ft.Row(
            [
                pill_button(
                    "提前 0.1s",
                    "歌词提前 100ms",
                    lambda e: on_adjust(LYRIC_OFFSET_STEP_FINE),
                ),
                pill_button(
                    "延后 0.1s",
                    "歌词延后 100ms",
                    lambda e: on_adjust(-LYRIC_OFFSET_STEP_FINE),
                ),
                pill_button(
                    "提前 1s",
                    "歌词提前 1000ms",
                    lambda e: on_adjust(LYRIC_OFFSET_STEP_COARSE),
                ),
                pill_button(
                    "延后 1s",
                    "歌词延后 1000ms",
                    lambda e: on_adjust(-LYRIC_OFFSET_STEP_COARSE),
                ),
                *(
                    [
                        reset_button(
                            "恢复歌词同步",
                            lambda e: (on_adjust(-offset), set_active("")),
                        )
                    ]
                    if sync_adjusted
                    else []
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=palette.SURFACE_SOFT,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
    )

    font_bar = ft.Container(
        content=ft.Row(
            [
                pill_button("A-", "缩小字号", lambda e: on_adjust_font(-1)),
                pill_button("A+", "增大字号", lambda e: on_adjust_font(1)),
                ft.Text(
                    f"{font_size:g}px",
                    size=11,
                    weight=ft.FontWeight.W_600,
                    color=palette.TEXT_DIM,
                    width=36,
                    text_align=ft.TextAlign.CENTER,
                ),
                *(
                    [
                        reset_button(
                            "恢复默认字号",
                            lambda e: (
                                on_adjust_font(LYRIC_FONT_DEFAULT - font_size),
                                set_active(""),
                            ),
                        )
                    ]
                    if font_changed
                    else []
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=palette.SURFACE_SOFT,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
    )

    return ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Container(expand=True),
                        sync_toggle,
                        font_toggle,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.only(left=28, right=28, top=2, bottom=4),
            ),
            ft.AnimatedSwitcher(
                content=(
                    sync_bar
                    if sync_active
                    else font_bar
                    if font_active
                    else ft.Container()
                ),
                transition=ft.AnimatedSwitcherTransition.FADE,
                duration=200,
                switch_in_curve=ft.AnimationCurve.EASE_OUT,
                switch_out_curve=ft.AnimationCurve.EASE_IN,
            ),
        ],
        spacing=0,
    )
