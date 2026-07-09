"""UI 组件：纯函数 + props 驱动，由 @ft.component 自动管理重渲染。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from .constants import (
    BRAND,
    BRAND_400,
    MODE_ICONS,
    SURFACE,
    SURFACE_SOFT,
    TEXT_DIM,
    TEXT_MAIN,
)
from .audio_player import Track


def _fmt(seconds: float) -> str:
    """秒数 → ``m:ss`` 格式。"""
    if seconds <= 0 or seconds != seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def card(controls: list[ft.Control], *, soft: bool = False) -> ft.Container:
    """统一的圆角卡片容器。"""
    return ft.Container(
        content=ft.Column(controls, spacing=12),
        bgcolor=SURFACE_SOFT if soft else SURFACE,
        border_radius=16,
        padding=20,
    )


# ── 播放列表 ── #


@ft.component
def PlaylistItem(
    track: Track,
    index: int,
    is_current: bool,
    on_click: Callable[[int], None],
) -> ft.Control:
    async def _on_click(e: ft.ControlEvent) -> None:
        await on_click(index)

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.GRAPHIC_EQ if is_current else ft.Icons.MUSIC_NOTE,
                    color=BRAND_400 if is_current else TEXT_DIM,
                    size=20,
                ),
                ft.Column(
                    [
                        ft.Text(
                            track.title,
                            size=14,
                            weight=ft.FontWeight.BOLD
                            if is_current
                            else ft.FontWeight.NORMAL,
                            color=TEXT_MAIN if is_current else TEXT_DIM,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            track.path.parent.name,
                            size=11,
                            color=ft.Colors.GREY_600,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=ft.Colors.with_opacity(0.18, BRAND)
        if is_current
        else ft.Colors.TRANSPARENT,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        on_click=_on_click,
        ink=True,
    )


@ft.component
def Playlist(
    tracks: list[Track],
    current: int,
    on_select: Callable[[int], None],
) -> ft.Control:
    if not tracks:
        return card(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.QUEUE_MUSIC, color=TEXT_DIM),
                        ft.Text("播放列表为空，点击右上角导入音乐", color=TEXT_DIM),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            ]
        )

    return card(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.QUEUE_MUSIC, color=BRAND_400),
                    ft.Text(
                        f"播放列表（{len(tracks)}）",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_MAIN,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ListView(
                controls=[
                    PlaylistItem(t, i, i == current, on_select)
                    for i, t in enumerate(tracks)
                ],
                spacing=4,
                padding=4,
                expand=True,
                height=320,
            ),
        ]
    )


# ── 进度条 ── #


@ft.component
def ProgressBar(
    position: float,
    duration: float,
    dragging: ft.MutableRef[bool],
    on_seek: Callable[[float], None],
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
        local_value
        if dragging.current
        else (position / duration if duration > 0 else 0.0)
    )

    return ft.Column(
        [
            ft.Slider(
                min=0,
                max=1,
                value=value,
                active_color=BRAND_400,
                thumb_color=BRAND,
                on_change=on_change,
                on_change_end=on_change_end,
                expand=True,
            ),
            ft.Row(
                [
                    ft.Text(_fmt(position), size=12, color=TEXT_DIM),
                    ft.Container(expand=True),
                    ft.Text(_fmt(duration), size=12, color=TEXT_DIM),
                ]
            ),
        ],
        spacing=2,
    )


# ── 音量控制 ── #


@ft.component
def VolumeControl(volume: float, on_change: Callable[[float], None]) -> ft.Control:
    icon = (
        ft.Icons.VOLUME_MUTE
        if volume == 0
        else ft.Icons.VOLUME_DOWN
        if volume < 0.5
        else ft.Icons.VOLUME_UP
    )
    return ft.Row(
        [
            ft.Icon(icon, color=BRAND_400, size=22),
            ft.Slider(
                min=0,
                max=1,
                value=volume,
                active_color=BRAND_400,
                thumb_color=BRAND,
                on_change=lambda e: on_change(float(e.control.value)),
                width=130,
            ),
        ],
        spacing=8,
    )


# ── 播放控制按钮组 ── #


@ft.component
def PlayControls(
    is_playing: bool,
    mode: str,
    has_tracks: bool,
    on_toggle: Callable,
    on_prev: Callable,
    on_next: Callable,
    on_mode: Callable,
) -> ft.Control:
    return ft.Row(
        [
            ft.IconButton(
                icon=MODE_ICONS[mode],
                icon_color=BRAND_400,
                tooltip=mode,
                on_click=on_mode,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_PREVIOUS_ROUNDED,
                icon_color=TEXT_MAIN,
                icon_size=36,
                tooltip="上一曲",
                on_click=on_prev,
            ),
            ft.IconButton(
                icon=ft.Icons.PAUSE_CIRCLE_FILLED_ROUNDED
                if is_playing
                else ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
                icon_color=BRAND_400,
                icon_size=56,
                tooltip="播放/暂停",
                on_click=on_toggle,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_NEXT_ROUNDED,
                icon_color=TEXT_MAIN,
                icon_size=36,
                tooltip="下一曲",
                on_click=on_next,
            ),
            ft.Container(
                content=ft.Text(
                    "♪" if has_tracks else "",
                    size=18,
                    color=ft.Colors.with_opacity(0.4, BRAND_400),
                ),
                width=44,
                alignment=ft.Alignment.CENTER,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=18,
    )


# ── 正在播放信息 ── #


@ft.component
def NowPlaying(track: Track | None, is_playing: bool) -> ft.Control:
    title = "未选择歌曲" if track is None else track.title
    subtitle = "请导入音乐文件夹" if track is None else track.path.parent.name
    return ft.Row(
        [
            ft.Container(
                content=ft.Icon(
                    ft.Icons.GRAPHIC_EQ if is_playing else ft.Icons.ALBUM,
                    size=64,
                    color=BRAND_400,
                ),
                width=96,
                height=96,
                alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.with_opacity(0.15, BRAND),
                border_radius=16,
            ),
            ft.Column(
                [
                    ft.Text(
                        title,
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_MAIN,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(subtitle, size=13, color=TEXT_DIM),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
        ],
        alignment=ft.MainAxisAlignment.START,
        spacing=18,
    )
