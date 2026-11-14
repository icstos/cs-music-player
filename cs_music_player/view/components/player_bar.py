"""底部播放栏：进度、播放控制、倍速、音量。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from ui import (
    Container,
    Icons,
    Row,
    SPACE,
    Text,
    disabled_layer,
    ft,
    selected_layer,
    state_layer,
)

from ...models import SPEED_PRESETS, Track
from .. import tokens as t
from ..theme import PLAY_MODE_ICONS
from .cover import track_cover
from .format import _fmt, _fmt_speed

__all__ = [
    "PlayControls",
    "PlayerBar",
    "ProgressBar",
    "SpeedControl",
    "VolumeControl",
]

RefT = TypeVar("RefT")


class MutableRef(Protocol[RefT]):
    """``ft.use_ref`` 返回的可变引用。

    Flet 只在 ``flet.components.hooks.use_ref`` 里定义 ``MutableRef``，没有在
    顶层导出；这里按结构声明一个等价的最小契约（只需要稳定的 ``current``），
    既准确又不依赖 Flet 的内部模块路径。
    """

    current: RefT


def _clamp_progress_value(value: float, duration: float) -> float:
    """将播放进度限制在 Slider 合法范围内，避免浮点误差导致越界。"""
    if duration <= 0:
        return 0.0
    ratio = value / duration
    if ratio != ratio:  # NaN
        return 0.0
    return max(0.0, min(1.0, ratio))


# ── 进度条 ── #


@ft.component
def ProgressBar(
    position: float,
    duration: float,
    dragging: MutableRef[bool],
    on_seek: Callable[[float], None],
    *,
    compact: bool = False,
) -> ft.Control:
    """进度：拖动时只改本地值，松手才 seek。

    拖动过程中每 100ms 发一次 seek 会让音频后端不停重定位（听感是「卡带」）；
    松手才真正跳，是播放器的通行做法。
    """
    local_value, set_local = ft.use_state(0.0)

    def on_change(e: ft.ControlEvent) -> None:
        set_local(float(e.control.value))
        dragging.current = True

    async def on_change_end(e: ft.ControlEvent) -> None:
        if duration > 0:
            await on_seek(float(e.control.value) * duration)
        dragging.current = False

    value = (
        local_value if dragging.current else _clamp_progress_value(position, duration)
    )

    slider = ft.Slider(
        min=0,
        max=1,
        value=value,
        active_color=t.TRACK_ACTIVE,
        inactive_color=t.TRACK,
        on_change=on_change,
        on_change_end=on_change_end,
        expand=True,
    )

    if compact:
        return Row(
            controls=[
                Text(
                    _fmt(position),
                    size=11,
                    color=t.TEXT_SOFT,
                    width=40,
                    text_align=ft.TextAlign.RIGHT,
                ),
                slider,
                Text(
                    _fmt(duration),
                    size=11,
                    color=t.TEXT_SOFT,
                    width=40,
                ),
            ],
            spacing=SPACE["1"],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Column(
        controls=[
            slider,
            Row(
                controls=[
                    Text(_fmt(position), size=11, color=t.TEXT_SOFT),
                    Container(expand=True),
                    Text(_fmt(duration), size=11, color=t.TEXT_SOFT),
                ],
            ),
        ],
        spacing=2,
    )


# ── 音量 ── #


@ft.component
def VolumeControl(
    volume: float, on_change: Callable[[float], None], *, compact: bool = False
) -> ft.Control:
    """音量：图标点击静音 / 恢复，滑块连续调节。

    「点图标静音」是播放器里唯一零成本且必须有的快捷操作——比把滑块拖到 0 精确，
    也比找系统音量快。恢复时回到静音前的值，而不是固定 50%。
    """
    muted, set_muted = ft.use_state(False)
    restore, set_restore = ft.use_state(0.7)

    def on_slider(event: ft.ControlEvent) -> None:
        """拖动滑块：任何手动调节都视为「解除静音」。"""
        set_muted(False)
        on_change(float(event.control.value))

    def toggle_mute() -> None:
        if volume > 0:
            set_restore(volume)
            set_muted(True)
            on_change(0.0)
        else:
            set_muted(False)
            on_change(restore or 0.7)

    icon = (
        Icons.VOLUME_OFF
        if volume == 0
        else Icons.VOLUME_DOWN
        if volume < 0.5
        else Icons.VOLUME_UP
    )
    return Row(
        controls=[
            ft.IconButton(
                icon=icon,
                icon_color=ft.Colors.PRIMARY if muted or volume == 0 else t.TEXT_SOFT,
                icon_size=20,
                tooltip="取消静音" if volume == 0 else "静音",
                on_click=lambda e: toggle_mute(),
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            ft.Slider(
                min=0,
                max=1,
                value=volume,
                active_color=t.TRACK_ACTIVE,
                inactive_color=t.TRACK,
                on_change=on_slider,
                width=100 if compact else 120,
            ),
        ],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


# ── 播放控制 ── #


@ft.component
def PlayControls(
    is_playing: bool,
    mode: str,
    has_tracks: bool,
    on_toggle: Callable[[ft.ControlEvent], None],
    on_prev: Callable[[ft.ControlEvent], None],
    on_next: Callable[[ft.ControlEvent], None],
    on_mode: Callable[[ft.ControlEvent], None],
    *,
    compact: bool = False,
) -> ft.Control:
    """上一首 / 播放暂停 / 下一首 / 播放模式。

    播放键是整条栏里唯一的主色实心圆：它是最高频的操作，视觉重量应该最大。
    """
    play_size = 44 if compact else 52
    skip_size = 26 if compact else 30
    play_icon_size = 24 if compact else 28
    play_icon = Icons.PAUSE_ROUNDED if is_playing else Icons.PLAY_ARROW_ROUNDED

    play_fg = ft.Colors.ON_PRIMARY if has_tracks else disabled_layer()
    icon: ft.Control = ft.Icon(play_icon, color=play_fg, size=play_icon_size)
    if not is_playing:
        # 播放三角形自带右边距的视觉错觉：往右补 2px 才看起来居中
        icon = Container(content=icon, margin=ft.Margin.only(left=2))

    return Row(
        controls=[
            ft.IconButton(
                icon=PLAY_MODE_ICONS[mode],
                icon_color=ft.Colors.PRIMARY if has_tracks else t.TEXT_SOFT,
                icon_size=20,
                tooltip=mode,
                on_click=on_mode,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(6)),
            ),
            ft.IconButton(
                icon=Icons.SKIP_PREVIOUS_ROUNDED,
                icon_color=t.TEXT if has_tracks else t.TEXT_SOFT,
                icon_size=skip_size,
                tooltip="上一曲",
                on_click=on_prev,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            Container(
                content=icon,
                width=play_size,
                height=play_size,
                alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.PRIMARY if has_tracks else disabled_layer("container"),
                border_radius=play_size // 2,
                on_click=on_toggle if has_tracks else None,
                ink=has_tracks,
                tooltip="播放" if not is_playing else "暂停",
            ),
            ft.IconButton(
                icon=Icons.SKIP_NEXT_ROUNDED,
                icon_color=t.TEXT if has_tracks else t.TEXT_SOFT,
                icon_size=skip_size,
                tooltip="下一曲",
                on_click=on_next,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=SPACE["1"] if compact else SPACE["2"],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


# ── 倍速 ── #


@ft.component
def SpeedControl(
    speed: float,
    on_change: Callable[[float], None],
) -> ft.Control:
    """倍速：紧凑按钮显示当前速度，点击弹出预设菜单（非默认值高亮）。"""
    is_default = speed == 1.0

    items: list[ft.PopupMenuItem] = []
    for preset in SPEED_PRESETS:
        selected = abs(speed - preset) < 1e-9
        items.append(
            ft.PopupMenuItem(
                content=Row(
                    controls=[
                        ft.Icon(
                            Icons.CHECK if selected else Icons.RADIO_BUTTON_UNCHECKED,
                            size=15,
                            color=ft.Colors.PRIMARY if selected else t.TEXT_SOFT,
                        ),
                        Text(
                            _fmt_speed(preset),
                            size=12,
                            weight=ft.FontWeight.W_600
                            if selected
                            else ft.FontWeight.NORMAL,
                            color=t.TEXT if selected else t.TEXT_SOFT,
                        ),
                    ],
                    spacing=SPACE["2"],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda e, rate=preset: on_change(rate),
            )
        )

    return ft.PopupMenuButton(
        content=Container(
            content=Text(
                _fmt_speed(speed),
                size=11,
                weight=ft.FontWeight.W_600,
                color=t.TEXT_SOFT if is_default else ft.Colors.PRIMARY,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=ft.Colors.TRANSPARENT
            if is_default
            else selected_layer("normal"),
        ),
        items=items,
        tooltip="播放速度",
        menu_position=ft.PopupMenuPosition.UNDER,
        style=ft.ButtonStyle(padding=ft.Padding.all(2)),
    )


# ── 整条播放栏 ── #


@ft.component
def PlayerBar(
    track: Track | None,
    is_playing: bool,
    position: float,
    duration: float,
    volume: float,
    speed: float,
    mode: str,
    dragging: MutableRef[bool],
    on_toggle: Callable[[ft.ControlEvent], None],
    on_prev: Callable[[ft.ControlEvent], None],
    on_next: Callable[[ft.ControlEvent], None],
    on_mode: Callable[[ft.ControlEvent], None],
    on_seek: Callable[[float], None],
    on_volume: Callable[[float], None],
    on_speed: Callable[[float], None],
) -> ft.Control:
    """底部固定栏：左「这首歌是什么」、中「放到哪」、右「怎么放」。"""
    title = "未选择歌曲" if track is None else track.title
    subtitle = "导入音乐文件夹开始播放" if track is None else track.path.parent.name

    return Container(
        content=Row(
            controls=[
                Row(
                    controls=[
                        track_cover(
                            track,
                            size=46,
                            is_playing=is_playing,
                            letter_fallback=True,
                        ),
                        ft.Column(
                            controls=[
                                Text(
                                    title,
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=t.TEXT,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                Text(
                                    subtitle,
                                    size=11,
                                    color=t.TEXT_SOFT,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2,
                            alignment=ft.MainAxisAlignment.CENTER,
                            tight=True,
                        ),
                    ],
                    spacing=SPACE["3"],
                    width=260,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                Container(
                    content=ProgressBar(
                        position, duration, dragging, on_seek, compact=True
                    ),
                    expand=True,
                    margin=ft.Margin.only(left=SPACE["2"], right=SPACE["2"]),
                ),
                Row(
                    controls=[
                        PlayControls(
                            is_playing,
                            mode,
                            track is not None,
                            on_toggle,
                            on_prev,
                            on_next,
                            on_mode,
                            compact=True,
                        ),
                        Container(width=SPACE["2"]),
                        SpeedControl(speed, on_speed),
                        Container(width=SPACE["1"]),
                        VolumeControl(volume, on_volume, compact=True),
                    ],
                    spacing=SPACE["1"],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=SPACE["3"],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=t.PANEL,
        border=ft.Border(top=ft.BorderSide(1, t.LINE)),
        padding=ft.Padding.symmetric(horizontal=SPACE["5"], vertical=SPACE["3"]),
    )
