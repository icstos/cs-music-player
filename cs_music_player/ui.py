"""UI 组件：纯函数 + props 驱动，由 @ft.component 自动管理重渲染。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from .constants import (
    ACCENT,
    ACCENT_TINT_10,
    BG,
    BORDER,
    PRIMARY,
    PRIMARY_BG,
    PRIMARY_LIGHT,
    PRIMARY_TINT_08,
    PRIMARY_TINT_12,
    SURFACE,
    SURFACE_SOFT,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_MUTED,
    MODE_ICONS,
)
from .audio_player import Track
from .lyrics import LyricLine, current_line_index


def _fmt(seconds: float) -> str:
    """秒数 → ``m:ss`` 格式。"""
    if seconds <= 0 or seconds != seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _track_cover(
    track: Track | None,
    *,
    size: int,
    is_playing: bool = False,
    is_current: bool = False,
    letter_fallback: bool = False,
) -> ft.Control:
    """曲目封面：有内嵌图则显示，否则图标或首字母占位。"""
    letter = "♪" if track is None else (track.title[:1].upper() or "♪")
    if track and track.cover_src:
        return ft.Container(
            content=ft.Image(
                src=track.cover_src,
                width=size,
                height=size,
                fit=ft.BoxFit.COVER,
                gapless_playback=True,
                error_content=ft.Container(
                    content=ft.Text(
                        letter,
                        size=max(14, size // 2),
                        weight=ft.FontWeight.W_700,
                        color=SURFACE,
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
            ),
            width=size,
            height=size,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=max(8, size // 8),
        )

    if letter_fallback:
        return ft.Container(
            content=ft.Text(
                letter,
                size=max(14, size // 2),
                weight=ft.FontWeight.W_700,
                color=SURFACE,
            ),
            width=size,
            height=size,
            alignment=ft.Alignment.CENTER,
            bgcolor=ACCENT if is_playing else PRIMARY,
            border_radius=max(8, size // 8),
        )

    return ft.Container(
        content=ft.Icon(
            ft.Icons.GRAPHIC_EQ if is_current and is_playing else ft.Icons.MUSIC_NOTE,
            color=PRIMARY if is_current else TEXT_MUTED,
            size=max(16, size // 2),
        ),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor=PRIMARY_TINT_12 if is_current else SURFACE_SOFT,
        border_radius=max(8, size // 8),
    )


# ── 播放列表 ── #


@ft.component
def PlaylistItem(
    index: int,
    track: Track,
    is_selected: bool,
    is_playing: bool,
    on_select: Callable[[Track], None],
    on_play: Callable[[Track], None],
    on_favorite: Callable[[Track], None],
) -> ft.Control:
    def _on_select(e: ft.ControlEvent) -> None:
        on_select(track)

    async def _on_play(e: ft.ControlEvent) -> None:
        await on_play(track)

    async def _on_favorite(e: ft.ControlEvent) -> None:
        await on_favorite(track)

    row = ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    f"{index + 1:02d}",
                    size=12,
                    color=PRIMARY_LIGHT if is_selected else TEXT_MUTED,
                    width=28,
                    text_align=ft.TextAlign.CENTER,
                ),
                _track_cover(track, size=40, is_current=is_selected, is_playing=is_playing),
                ft.Column(
                    [
                        ft.Text(
                            track.title,
                            size=13,
                            weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_500,
                            color=TEXT_MAIN if is_selected else TEXT_DIM,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            track.path.parent.name,
                            size=11,
                            color=TEXT_MUTED,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.FAVORITE if track.favorite else ft.Icons.FAVORITE_BORDER,
                    icon_color=PRIMARY_LIGHT if track.favorite else TEXT_MUTED,
                    icon_size=18,
                    tooltip="取消收藏" if track.favorite else "收藏",
                    on_click=_on_favorite,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.all(4),
                        overlay_color=ft.Colors.with_opacity(0.06, PRIMARY),
                    ),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=PRIMARY_BG if is_selected else ft.Colors.TRANSPARENT,
        border=ft.Border(
            left=ft.BorderSide(3, PRIMARY if is_selected else ft.Colors.TRANSPARENT),
        ),
        padding=ft.Padding.only(left=8, right=8, top=6, bottom=6),
        ink=True,
    )

    return ft.GestureDetector(
        on_tap=_on_select,
        on_double_tap=_on_play,
        content=row,
    )


@ft.component
def Sidebar(
    tracks: list[Track],
    selected: int,
    playing_track: Track | None,
    search: str,
    show_favorites: bool,
    total_count: int,
    on_search: Callable[[str], None],
    on_toggle_favorites: Callable[[bool], None],
    on_select: Callable[[Track], None],
    on_play: Callable[[Track], None],
    on_favorite: Callable[[Track], None],
    is_playing: bool,
    on_search_focus: Callable[[], None],
    on_search_blur: Callable[[], None],
) -> ft.Control:
    selected_track = tracks[selected] if 0 <= selected < len(tracks) else None

    header = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("音乐库", size=16, weight=ft.FontWeight.W_700, color=TEXT_MAIN),
                        ft.Container(expand=True),
                        ft.Text(
                            f"{len(tracks)} / {total_count} 首",
                            size=11,
                            color=TEXT_MUTED,
                        ),
                    ],
                ),
                ft.TextField(
                    value=search,
                    on_change=lambda e: on_search(str(e.control.value or "")),
                    on_focus=lambda e: on_search_focus(),
                    on_blur=lambda e: on_search_blur(),
                    hint_text="搜索歌曲或文件夹",
                    prefix_icon=ft.Icons.SEARCH,
                    border_radius=12,
                    dense=True,
                    content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_color=BORDER,
                    focused_border_color=PRIMARY_LIGHT,
                    bgcolor=SURFACE,
                ),
                ft.Row(
                    [
                        ft.Chip(
                            label=ft.Text("全部", size=12),
                            selected=not show_favorites,
                            on_select=lambda e: on_toggle_favorites(False),
                        ),
                        ft.Chip(
                            label=ft.Text("收藏", size=12),
                            leading=ft.Icon(ft.Icons.FAVORITE, size=16),
                            selected=show_favorites,
                            on_select=lambda e: on_toggle_favorites(True),
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
        ),
        padding=ft.Padding.only(left=16, right=16, top=16, bottom=12),
        border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
    )

    if not tracks:
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.LIBRARY_MUSIC_OUTLINED, size=48, color=TEXT_MUTED),
                    ft.Text("暂无歌曲", size=14, weight=ft.FontWeight.W_600, color=TEXT_DIM),
                    ft.Text("点击右上角导入音乐文件夹", size=12, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        body = ft.ListView(
            controls=[
                PlaylistItem(
                    i,
                    t,
                    t is selected_track,
                    is_playing and t is playing_track,
                    on_select,
                    on_play,
                    on_favorite,
                )
                for i, t in enumerate(tracks)
            ],
            spacing=2,
            padding=ft.Padding.symmetric(vertical=8),
            expand=True,
        )

    return ft.Container(
        content=ft.Column([header, body], spacing=0, expand=True),
        width=340,
        bgcolor=SURFACE,
        border=ft.Border(right=ft.BorderSide(1, BORDER)),
        expand=False,
    )


# ── 进度条 ── #


@ft.component
def ProgressBar(
    position: float,
    duration: float,
    dragging: ft.MutableRef[bool],
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
        local_value
        if dragging.current
        else (position / duration if duration > 0 else 0.0)
    )

    slider = ft.Slider(
        min=0,
        max=1,
        value=value,
        active_color=PRIMARY,
        inactive_color=BORDER,
        thumb_color=PRIMARY_LIGHT,
        on_change=on_change,
        on_change_end=on_change_end,
        expand=True,
    )

    if compact:
        return ft.Row(
            [
                ft.Text(_fmt(position), size=11, color=TEXT_MUTED, width=36),
                slider,
                ft.Text(_fmt(duration), size=11, color=TEXT_MUTED, width=36, text_align=ft.TextAlign.RIGHT),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Column(
        [
            slider,
            ft.Row(
                [
                    ft.Text(_fmt(position), size=11, color=TEXT_MUTED),
                    ft.Container(expand=True),
                    ft.Text(_fmt(duration), size=11, color=TEXT_MUTED),
                ]
            ),
        ],
        spacing=2,
    )


# ── 音量控制 ── #


@ft.component
def VolumeControl(volume: float, on_change: Callable[[float], None], *, compact: bool = False) -> ft.Control:
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
                icon_color=TEXT_DIM,
                icon_size=20,
                tooltip="音量",
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            ft.Slider(
                min=0,
                max=1,
                value=volume,
                active_color=PRIMARY,
                inactive_color=BORDER,
                thumb_color=PRIMARY_LIGHT,
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
    on_toggle: Callable,
    on_prev: Callable,
    on_next: Callable,
    on_mode: Callable,
    *,
    compact: bool = False,
) -> ft.Control:
    play_size = 44 if compact else 52
    skip_size = 28 if compact else 32
    play_icon_size = 26 if compact else 30
    play_icon = ft.Icons.PAUSE_ROUNDED if is_playing else ft.Icons.PLAY_ARROW_ROUNDED
    play_icon_control: ft.Control = ft.Icon(play_icon, color=SURFACE, size=play_icon_size)
    if not is_playing:
        play_icon_control = ft.Container(
            content=play_icon_control,
            margin=ft.Margin.only(left=2),
        )
    return ft.Row(
        [
            ft.IconButton(
                icon=MODE_ICONS[mode],
                icon_color=PRIMARY if has_tracks else TEXT_MUTED,
                icon_size=22,
                tooltip=mode,
                on_click=on_mode,
                disabled=not has_tracks,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_PREVIOUS_ROUNDED,
                icon_color=TEXT_MAIN if has_tracks else TEXT_MUTED,
                icon_size=skip_size,
                tooltip="上一曲",
                on_click=on_prev,
                disabled=not has_tracks,
            ),
            ft.Container(
                content=play_icon_control,
                width=play_size,
                height=play_size,
                alignment=ft.Alignment.CENTER,
                bgcolor=PRIMARY if has_tracks else TEXT_MUTED,
                border_radius=play_size // 2,
                on_click=on_toggle if has_tracks else None,
                ink=True,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=12,
                    color=ft.Colors.with_opacity(0.2, PRIMARY),
                    offset=ft.Offset(0, 4),
                ) if has_tracks else None,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_NEXT_ROUNDED,
                icon_color=TEXT_MAIN if has_tracks else TEXT_MUTED,
                icon_size=skip_size,
                tooltip="下一曲",
                on_click=on_next,
                disabled=not has_tracks,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=4 if compact else 8,
    )


# ── 底部播放栏 ── #


@ft.component
def PlayerBar(
    track: Track | None,
    is_playing: bool,
    position: float,
    duration: float,
    volume: float,
    mode: str,
    dragging: ft.MutableRef[bool],
    on_toggle: Callable,
    on_prev: Callable,
    on_next: Callable,
    on_mode: Callable,
    on_seek: Callable[[float], None],
    on_volume: Callable[[float], None],
) -> ft.Control:
    title = "未选择歌曲" if track is None else track.title
    subtitle = "导入音乐文件夹开始播放" if track is None else track.path.parent.name

    return ft.Container(
        content=ft.Column(
            [
                ProgressBar(position, duration, dragging, on_seek, compact=True),
                ft.Row(
                    [
                        ft.Row(
                            [
                                _track_cover(
                                    track,
                                    size=52,
                                    is_playing=is_playing,
                                    letter_fallback=True,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            title,
                                            size=14,
                                            weight=ft.FontWeight.W_600,
                                            color=TEXT_MAIN,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            subtitle,
                                            size=11,
                                            color=TEXT_MUTED,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                    spacing=2,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=12,
                            width=280,
                        ),
                        ft.Container(expand=True),
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
                        ft.Container(expand=True),
                        VolumeControl(volume, on_volume, compact=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=6,
        ),
        bgcolor=SURFACE,
        border=ft.Border(top=ft.BorderSide(1, BORDER)),
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color=ft.Colors.with_opacity(0.04, "#0f172a"),
            offset=ft.Offset(0, -4),
        ),
    )


# ── 歌词面板 ── #


@ft.component
def LyricsLine(
    text: str,
    is_current: bool,
) -> ft.Control:
    return ft.Container(
        content=ft.Text(
            text,
            size=18 if is_current else 15,
            weight=ft.FontWeight.W_700 if is_current else ft.FontWeight.NORMAL,
            color=PRIMARY if is_current else TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        padding=ft.Padding.symmetric(vertical=6 if is_current else 4),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


@ft.component
def LyricsPanel(
    lines: list[LyricLine],
    position: float,
    has_lyrics_file: bool,
) -> ft.Control:
    active = current_line_index(lines, position)

    if not has_lyrics_file:
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=36, color=TEXT_MUTED),
                    ft.Text("暂无歌词", size=13, color=TEXT_DIM),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    elif not lines:
        body = ft.Container(
            content=ft.Text("歌词文件无法解析", size=13, color=TEXT_DIM),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        body = ft.Container(
            content=ft.Column(
                controls=[
                    LyricsLine(line.text, i == active)
                    for i, line in enumerate(lines)
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
            padding=ft.Padding.symmetric(horizontal=24),
        )

    return body


# ── 主舞台（封面 + 歌词） ── #


@ft.component
def MainStage(
    track: Track | None,
    is_playing: bool,
    lyrics: list[LyricLine],
    position: float,
    has_lyrics_file: bool,
) -> ft.Control:
    title = "未选择歌曲" if track is None else track.title
    subtitle = "请导入音乐文件夹" if track is None else track.path.parent.name
    cover_size = 220

    cover = ft.Container(
        content=_track_cover(
            track,
            size=cover_size,
            is_playing=is_playing,
            letter_fallback=True,
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=32,
            color=ft.Colors.with_opacity(0.15, "#0f172a"),
            offset=ft.Offset(0, 12),
        ),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
    )

    if track and is_playing:
        cover = ft.Container(
            content=ft.Stack(
                [
                    cover,
                    ft.Container(
                        content=ft.Icon(ft.Icons.GRAPHIC_EQ, color=ACCENT, size=20),
                        alignment=ft.Alignment(1, -1),
                        margin=ft.Margin.only(top=8, right=8),
                        bgcolor=ACCENT_TINT_10,
                        border_radius=20,
                        padding=ft.Padding.all(6),
                    ),
                ],
            ),
        )

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            cover,
                            ft.Container(height=8),
                            ft.Text(
                                title,
                                size=22,
                                weight=ft.FontWeight.W_700,
                                color=TEXT_MAIN,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                subtitle,
                                size=13,
                                color=TEXT_DIM,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=ft.Padding.only(top=32, bottom=16),
                ),
                ft.Container(
                    content=LyricsPanel(lyrics, position, has_lyrics_file),
                    expand=True,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        ),
        expand=True,
        bgcolor=BG,
        padding=ft.Padding.symmetric(horizontal=32),
    )
