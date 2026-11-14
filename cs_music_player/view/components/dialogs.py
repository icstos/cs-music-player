"""弹窗：睡眠定时器配置。"""

from __future__ import annotations

from collections.abc import Callable

from ui import (
    Container,
    Icons,
    Row,
    SPACE,
    StyleType,
    Button,
    Text,
    ft,
)

from ...models import SLEEP_PRESET_MINUTES
from .. import tokens as t
from .format import fmt_duration

__all__ = ["build_sleep_dialog"]


def build_sleep_dialog(
    remaining: float,
    on_start: Callable[[int], None],
    on_cancel: Callable[[], None],
    on_close: Callable[[], None],
) -> ft.AlertDialog:
    """睡眠定时器配置弹窗：快捷预设 + 时/分/秒自定义，激活时可查看剩余并取消。

    预设给「马上就睡」的人，自定义给「听完这一张专辑」的人；两行并列，不用先选
    模式再填数。已激活时在底部补一条剩余时间——否则用户得去猜还剩多久。
    """
    hours_ref: ft.Ref[ft.TextField] = ft.Ref()
    minutes_ref: ft.Ref[ft.TextField] = ft.Ref()
    seconds_ref: ft.Ref[ft.TextField] = ft.Ref()

    def _field(ref: ft.Ref[ft.TextField], label: str) -> ft.TextField:
        return ft.TextField(
            ref=ref,
            label=label,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=68,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=8),
        )

    def start_custom(e: ft.ControlEvent) -> None:
        def _value(ref: ft.Ref[ft.TextField]) -> int:
            try:
                return int((ref.current.value or "").strip() or 0)
            except (TypeError, ValueError):
                return 0

        total = _value(hours_ref) * 3600 + _value(minutes_ref) * 60 + _value(seconds_ref)
        if total > 0:
            on_start(total)

    presets = ft.Row(
        controls=[
            ft.Chip(
                label=Text(f"{minutes} 分钟", size=12),
                on_select=lambda e, m=minutes: on_start(m * 60),
            )
            for minutes in SLEEP_PRESET_MINUTES
        ],
        spacing=SPACE["1"],
        wrap=True,
        # 限宽让五个预设排成 3 + 2 两行：一行放不下五个，而「四个 + 一个」的
        # 落单最难看成有意为之。
        width=294,
    )

    custom = Row(
        controls=[
            _field(hours_ref, "时"),
            _field(minutes_ref, "分"),
            _field(seconds_ref, "秒"),
            Button(
                "开始",
                style_type=StyleType.PRIMARY,
                on_click=start_custom,
            ),
        ],
        spacing=SPACE["2"],
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    body: list[ft.Control] = [
        Text("倒计时结束后自动关闭软件", size=12, color=t.TEXT_SOFT),
        presets,
        ft.Divider(height=1, color=t.LINE),
        custom,
    ]
    if remaining > 0:
        body.extend(
            [
                ft.Divider(height=1, color=t.LINE),
                Row(
                    controls=[
                        ft.Icon(Icons.TIMER, size=16, color=t.ACCENT),
                        Text(
                            f"剩余 {fmt_duration(remaining)}",
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=t.ACCENT,
                        ),
                        Container(expand=True),
                        ft.TextButton(
                            content=Text("取消定时", size=12, color=t.TEXT_SOFT),
                            on_click=lambda e: on_cancel(),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ]
        )

    return ft.AlertDialog(
        modal=True,
        title=Text("睡眠定时器", size=16, weight=ft.FontWeight.W_600),
        content=Container(
            # tight：列高按内容算。Column 默认 mainAxisSize.max，会把弹窗
            # 撑到满高，下半截留一大片空白。
            # 330 = 「时 分 秒 + 开始」这一行所需宽度；再窄按钮就被挤到下一行。
            content=ft.Column(controls=body, spacing=SPACE["3"], width=330, tight=True),
            padding=ft.Padding.only(top=SPACE["1"]),
        ),
        actions=[
            ft.TextButton(
                content=Text("关闭", size=12, color=t.TEXT_SOFT),
                on_click=lambda e: on_close(),
            )
        ],
    )
