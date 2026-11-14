"""工具栏：桌面歌词入口与睡眠定时器入口。"""

from __future__ import annotations

from collections.abc import Callable

from ui import (
    BoxConstraints,
    ButtonStyle,
    Colors,
    Container,
    Control,
    CrossAxisAlignment,
    Divider,
    Icon,
    IconButton,
    IconData,
    Icons,
    Padding,
    PopupMenuButton,
    PopupMenuItem,
    PopupMenuPosition,
    Row,
    SPACE,
    Text,
    component,
    state_layer,
)

from .. import tokens as t
from .format import fmt_duration

__all__ = ["DesktopLyricButton", "SleepTimerButton"]


# ── 桌面歌词入口 ── #


@component
def DesktopLyricButton(
    enabled: bool,
    locked: bool,
    font_size: float,
    on_toggle: Callable[[], None],
    on_toggle_lock: Callable[[], None],
    on_font_step: Callable[[float], None],
    on_reset_font: Callable[[], None],
    on_close: Callable[[], None],
) -> Control:
    """工具栏上的桌面歌词入口。

    开关、锁定、字号都收在一个菜单里：桌面歌词的浮窗本身就是「无边框、可穿透」
    的，主界面必须留一条随时能把它收回来 / 解锁的路——否则锁定后用户就再也点
    不到它了。
    """
    active = enabled

    def item(
        icon: IconData,
        label: str,
        on_click: Callable[[], None],
        *,
        accent: bool = False,
        hint: str = "",
    ) -> PopupMenuItem:
        return PopupMenuItem(
            content=Row(
                controls=[
                    Icon(
                        icon,
                        size=16,
                        color=t.ACCENT if accent else t.TEXT_SOFT,
                    ),
                    Text(label, size=12, color=t.TEXT),
                    Container(expand=True),
                    Text(hint, size=11, color=t.TEXT_SOFT)
                    if hint
                    else Container(),
                ],
                spacing=SPACE["2"],
                vertical_alignment=CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e: on_click(),
        )

    def divider() -> PopupMenuItem:
        return PopupMenuItem(content=Divider(height=1, color=t.LINE), height=1)

    items: list[PopupMenuItem] = [
        item(
            Icons.CLOSE if enabled else Icons.SUBTITLES,
            "隐藏桌面歌词" if enabled else "显示桌面歌词",
            on_toggle,
            accent=enabled,
            hint="已开启" if enabled else "已关闭",
        )
    ]
    if enabled:
        items.append(
            item(
                Icons.LOCK if locked else Icons.LOCK_OPEN,
                "解锁歌词（可拖动、可操作）" if locked else "锁定歌词（鼠标穿透）",
                on_toggle_lock,
                accent=locked,
                hint="鼠标穿透中" if locked else "",
            )
        )
        items.append(divider())
        items.append(
            item(
                Icons.TEXT_INCREASE,
                "增大歌词字体",
                lambda: on_font_step(1.0),
                hint=f"{font_size:g}",
            )
        )
        items.append(
            item(Icons.TEXT_DECREASE, "减小歌词字体", lambda: on_font_step(-1.0))
        )
        items.append(item(Icons.RESTART_ALT, "恢复默认字体", on_reset_font))
        items.append(divider())
        items.append(item(Icons.POWER_SETTINGS_NEW, "关闭桌面歌词", on_close))

    tooltip = "桌面歌词"
    if enabled:
        tooltip = "桌面歌词（已开启" + ("，已锁定" if locked else "") + "）"

    return PopupMenuButton(
        icon=Icons.SUBTITLES if not active else Icons.SUBTITLES_ROUNDED,
        icon_color=Colors.PRIMARY if active else t.TEXT_SOFT,
        icon_size=22,
        tooltip=tooltip,
        style=ButtonStyle(padding=Padding.all(8)),
        menu_position=PopupMenuPosition.UNDER,
        size_constraints=BoxConstraints(min_width=252, max_width=252),
        items=items,
    )


@component
def SleepTimerButton(
    remaining: float,
    on_click: Callable[[], None],
) -> Control:
    """睡眠定时器入口：仅图标，激活时强调色提示。

    倒计时进行中把剩余时间写进 tooltip——不占版面，又把「还有多久」这个
    每次都会问的问题答了。
    """
    active = remaining > 0
    tooltip = (
        f"睡眠定时器（剩余 {fmt_duration(remaining)}）" if active else "睡眠定时器"
    )
    return IconButton(
        icon=Icons.BEDTIME if active else Icons.BEDTIME_OUTLINED,
        icon_color=t.ACCENT if active else t.TEXT_SOFT,
        icon_size=20,
        tooltip=tooltip,
        on_click=lambda e: on_click(),
        style=ButtonStyle(
            padding=Padding.all(8),
            overlay_color=state_layer("hover"),
        ),
    )
