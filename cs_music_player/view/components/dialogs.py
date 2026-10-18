"""弹窗：睡眠定时器配置。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ..theme import palette
from .format import fmt_duration
from ...models import SLEEP_PRESET_MINUTES

__all__ = ["build_sleep_dialog"]


def build_sleep_dialog(
    remaining: float,
    on_start: Callable[[int], None],
    on_cancel: Callable[[], None],
    on_close: Callable[[], None],
) -> ft.AlertDialog:
    """睡眠定时器配置弹窗：快捷预设 + 时/分/秒自定义，激活时可查看剩余并取消。"""
    hours_ref: ft.Ref[ft.TextField] = ft.Ref()
    minutes_ref: ft.Ref[ft.TextField] = ft.Ref()
    seconds_ref: ft.Ref[ft.TextField] = ft.Ref()

    def _field(ref: ft.Ref[ft.TextField], label: str) -> ft.TextField:
        return ft.TextField(
            ref=ref,
            label=label,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=66,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=8),
            border=ft.OutlineInputBorder(border_radius=8),
        )

    def start_custom(e: ft.ControlEvent) -> None:
        def _val(ref: ft.Ref[ft.TextField]) -> int:
            try:
                return int((ref.current.value or "").strip() or 0)
            except (TypeError, ValueError):
                return 0

        total = _val(hours_ref) * 3600 + _val(minutes_ref) * 60 + _val(seconds_ref)
        if total > 0:
            on_start(total)

    presets = ft.Row(
        [
            ft.Chip(
                label=ft.Text(f"{m} 分钟", size=12),
                on_select=lambda e, m=m: on_start(m * 60),
            )
            for m in SLEEP_PRESET_MINUTES
        ],
        spacing=6,
        wrap=True,
    )

    custom = ft.Row(
        [
            _field(hours_ref, "时"),
            _field(minutes_ref, "分"),
            _field(seconds_ref, "秒"),
            ft.FilledButton(
                content=ft.Text("开始", size=12),
                on_click=start_custom,
                style=ft.ButtonStyle(
                    bgcolor=palette.PRIMARY,
                    color=palette.ON_PRIMARY,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ),
            ),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    body: list[ft.Control] = [
        ft.Text("倒计时结束后自动关闭软件", size=12, color=palette.TEXT_DIM),
        ft.Container(height=4),
        presets,
        ft.Divider(height=1, color=palette.BORDER),
        custom,
    ]
    if remaining > 0:
        body.extend(
            [
                ft.Divider(height=1, color=palette.BORDER),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TIMER, size=16, color=palette.ACCENT),
                        ft.Text(
                            f"剩余 {fmt_duration(remaining)}",
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=palette.ACCENT,
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            content=ft.Text("取消定时", size=12, color=palette.TEXT_DIM),
                            on_click=lambda e: on_cancel(),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ]
        )

    return ft.AlertDialog(
        modal=True,
        title=ft.Text("睡眠定时器", size=16, weight=ft.FontWeight.W_700),
        content=ft.Container(
            # tight：列高按内容算。Column 默认 mainAxisSize.max，会把弹窗
            # 撑到满高，下半截留一大片空白。
            content=ft.Column(body, spacing=10, width=320, tight=True),
            padding=ft.Padding.only(top=4),
        ),
        actions=[
            ft.TextButton(
                content=ft.Text("关闭", size=12, color=palette.TEXT_DIM),
                on_click=lambda e: on_close(),
            )
        ],
    )
