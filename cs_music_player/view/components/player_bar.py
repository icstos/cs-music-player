"""底部播放栏：进度条、音量、播放控制、倍速。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

import flet as ft

from ...models import SPEED_PRESETS, Track
from ..theme import MODE_ICONS, palette
from .cover import _track_cover
from .format import _fmt, _fmt_speed

__all__ = [
    "ProgressBar",
    "VolumeControl",
    "PlayControls",
    "SpeedControl",
    "PlayerBar",
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
    if ratio != ratio:
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
        active_color=palette.PRIMARY,
        inactive_color=palette.BORDER,
        thumb_color=palette.PRIMARY_LIGHT,
        on_change=on_change,
        on_change_end=on_change_end,
        expand=True,
    )

    if compact:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(_fmt(position), size=10, color=palette.TEXT_MUTED, width=34),
                    slider,
                    ft.Text(
                        _fmt(duration),
                        size=10,
                        color=palette.TEXT_MUTED,
                        width=34,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.03, palette.PRIMARY),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )

    return ft.Column(
        [
            slider,
            ft.Row(
                [
                    ft.Text(_fmt(position), size=11, color=palette.TEXT_MUTED),
                    ft.Container(expand=True),
                    ft.Text(_fmt(duration), size=11, color=palette.TEXT_MUTED),
                ]
            ),
        ],
        spacing=2,
    )


# ── 音量控制 ── #


@ft.component
def VolumeControl(
    volume: float, on_change: Callable[[float], None], *, compact: bool = False
) -> ft.Control:
    icon = (
        ft.Icons.VOLUME_MUTE
        if volume == 0
        else ft.Icons.VOLUME_DOWN
        if volume < 0.5
        else ft.Icons.VOLUME_UP
    )
    slider_width = 100 if compact else 120
    return ft.Row(
        [
            ft.IconButton(
                icon=icon,
                icon_color=palette.TEXT_DIM,
                icon_size=20,
                tooltip="音量",
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            ft.Slider(
                min=0,
                max=1,
                value=volume,
                active_color=palette.PRIMARY,
                inactive_color=palette.BORDER,
                thumb_color=palette.PRIMARY_LIGHT,
                on_change=lambda e: on_change(float(e.control.value)),
                width=slider_width,
            ),
        ],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


# ── 播放控制按钮组 ── #


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
    play_size = 44 if compact else 52
    skip_size = 28 if compact else 32
    play_icon_size = 26 if compact else 30
    play_icon = ft.Icons.PAUSE_ROUNDED if is_playing else ft.Icons.PLAY_ARROW_ROUNDED
    play_icon_control: ft.Control = ft.Icon(
        play_icon, color=palette.SURFACE, size=play_icon_size
    )
    if not is_playing:
        play_icon_control = ft.Container(
            content=play_icon_control,
            margin=ft.Margin.only(left=2),
        )
    return ft.Row(
        [
            ft.Container(
                content=ft.IconButton(
                    icon=MODE_ICONS[mode],
                    icon_color=palette.PRIMARY if has_tracks else palette.TEXT_MUTED,
                    icon_size=20,
                    tooltip=mode,
                    on_click=on_mode,
                    disabled=not has_tracks,
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                ),
                bgcolor=ft.Colors.with_opacity(0.04, palette.PRIMARY),
                border_radius=10,
                padding=ft.Padding.all(2),
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_PREVIOUS_ROUNDED,
                icon_color=palette.TEXT_MAIN if has_tracks else palette.TEXT_MUTED,
                icon_size=skip_size,
                tooltip="上一曲",
                on_click=on_prev,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            ft.Container(
                content=play_icon_control,
                width=play_size,
                height=play_size,
                alignment=ft.Alignment.CENTER,
                bgcolor=palette.PRIMARY if has_tracks else palette.TEXT_MUTED,
                border_radius=play_size // 2,
                on_click=on_toggle if has_tracks else None,
                ink=True,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=12,
                    color=ft.Colors.with_opacity(0.2, palette.PRIMARY),
                    offset=ft.Offset(0, 4),
                )
                if has_tracks
                else None,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_NEXT_ROUNDED,
                icon_color=palette.TEXT_MAIN if has_tracks else palette.TEXT_MUTED,
                icon_size=skip_size,
                tooltip="下一曲",
                on_click=on_next,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=4 if compact else 8,
    )


# ── 播放速度 ── #


@ft.component
def SpeedControl(
    speed: float,
    on_change: Callable[[float], None],
) -> ft.Control:
    """倍速选择：紧凑按钮显示当前速度，点击弹出预设菜单。"""
    is_default = speed == 1.0

    items: list[ft.PopupMenuItem] = []
    for preset in SPEED_PRESETS:
        selected = abs(speed - preset) < 1e-9
        items.append(
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.CHECK
                            if selected
                            else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=15,
                            color=palette.PRIMARY if selected else palette.TEXT_MUTED,
                        ),
                        ft.Text(
                            _fmt_speed(preset),
                            size=12,
                            weight=ft.FontWeight.W_600
                            if selected
                            else ft.FontWeight.NORMAL,
                            color=palette.TEXT_MAIN if selected else palette.TEXT_DIM,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda e, r=preset: on_change(r),
            )
        )

    return ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Text(
                _fmt_speed(speed),
                size=11,
                weight=ft.FontWeight.W_600,
                color=palette.PRIMARY if not is_default else palette.TEXT_DIM,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=(
                palette.PRIMARY_TINT_12 if not is_default else ft.Colors.TRANSPARENT
            ),
        ),
        items=items,
        tooltip="播放速度",
        menu_position=ft.PopupMenuPosition.UNDER,
        style=ft.ButtonStyle(padding=ft.Padding.all(2)),
    )


# ── 底部播放栏 ── #


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
    title = "未选择歌曲" if track is None else track.title
    subtitle = "导入音乐文件夹开始播放" if track is None else track.path.parent.name

    return ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        _track_cover(
                            track,
                            size=46,
                            is_playing=is_playing,
                            letter_fallback=True,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    title,
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=palette.TEXT_MAIN,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    subtitle,
                                    size=10,
                                    color=palette.TEXT_MUTED,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=10,
                    width=260,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=ProgressBar(
                        position, duration, dragging, on_seek, compact=True
                    ),
                    expand=True,
                    margin=ft.Margin.only(left=8, right=8),
                ),
                ft.Row(
                    [
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
                        ft.Container(width=6),
                        SpeedControl(speed, on_speed),
                        ft.Container(width=4),
                        VolumeControl(volume, on_volume, compact=True),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=palette.SURFACE,
        border=ft.Border(top=ft.BorderSide(1, palette.BORDER)),
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color=ft.Colors.with_opacity(0.04, palette.TEXT_MAIN),
            offset=ft.Offset(0, -4),
        ),
    )
