"""播放列表：曲目信息悬浮卡、单曲行与侧边栏。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ...models import Track
from ..theme import palette
from .cover import _track_cover
from .format import _fmt, _fmt_bitrate, _fmt_frequency, _fmt_size, _kv

__all__ = ["PlaylistItem", "Sidebar"]


def _track_info_tooltip(track: Track) -> ft.Tooltip:
    """曲目信息悬浮卡：延迟出现、跟随光标、深色质感卡片。"""
    header = [
        f"♪　{track.title or track.path.name}",
        _kv("歌手", track.artist or "未知"),
    ]
    rows: list[str] = []
    if track.duration > 0:
        rows.append(_kv("时长", _fmt(track.duration)))
    if track.album:
        rows.append(_kv("专辑", track.album))
    size = _fmt_size(track.file_size)
    if size:
        rows.append(_kv("大小", size))
    freq = _fmt_frequency(track.sample_rate)
    if freq:
        rows.append(_kv("采样率", freq))
    bitrate = _fmt_bitrate(track.bitrate)
    if bitrate:
        rows.append(_kv("码率", bitrate))
    if track.channels:
        rows.append(_kv("声道", str(track.channels)))
    if track.audio_format:
        rows.append(_kv("格式", track.audio_format))

    body = "\n".join(header + (["─" * 15, *rows] if rows else []))
    return ft.Tooltip(
        message=body,
        text_style=ft.TextStyle(
            size=11.5,
            height=1.65,
            color=ft.Colors.WHITE,
            letter_spacing=0.2,
        ),
        text_align=ft.TextAlign.START,
        padding=ft.Padding.symmetric(horizontal=14, vertical=11),
        decoration=ft.BoxDecoration(
            bgcolor=ft.Colors.with_opacity(0.97, palette.PRIMARY_DARK),
            border_radius=ft.BorderRadius.all(10),
            border=ft.Border.all(
                1, ft.Colors.with_opacity(0.28, ft.Colors.WHITE)
            ),
            shadows=[
                ft.BoxShadow(
                    blur_radius=22,
                    color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                    offset=ft.Offset(0, 6),
                )
            ],
        ),
        size_constraints=ft.BoxConstraints(max_width=340),
        prefer_below=True,
        vertical_offset=10,
        wait_duration=ft.Duration(milliseconds=600),
        exit_duration=ft.Duration(milliseconds=120),
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
                    color=palette.PRIMARY_LIGHT if is_selected else palette.TEXT_MUTED,
                    width=28,
                    text_align=ft.TextAlign.CENTER,
                ),
                _track_cover(
                    track, size=40, is_current=is_selected, is_playing=is_playing
                ),
                ft.Column(
                    [
                        ft.Text(
                            track.title,
                            size=13,
                            weight=ft.FontWeight.W_600
                            if is_selected
                            else ft.FontWeight.W_500,
                            color=palette.TEXT_MAIN if is_selected else palette.TEXT_DIM,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    track.artist or track.path.parent.name,
                                    size=11,
                                    color=palette.TEXT_MUTED,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                ft.Text(
                                    _fmt(track.duration),
                                    size=11,
                                    color=palette.TEXT_MUTED,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.FAVORITE
                    if track.favorite
                    else ft.Icons.FAVORITE_BORDER,
                    icon_color=palette.PRIMARY_LIGHT if track.favorite else palette.TEXT_MUTED,
                    icon_size=18,
                    tooltip="取消收藏" if track.favorite else "收藏",
                    on_click=_on_favorite,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.all(4),
                        overlay_color=ft.Colors.with_opacity(0.06, palette.PRIMARY),
                    ),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=palette.PRIMARY_BG if is_selected else ft.Colors.TRANSPARENT,
        border=ft.Border(
            left=ft.BorderSide(3, palette.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
        ),
        padding=ft.Padding.only(left=8, right=8, top=6, bottom=6),
        ink=True,
    )

    return ft.GestureDetector(
        on_tap=_on_select,
        on_double_tap=_on_play,
        tooltip=_track_info_tooltip(track),
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
                        ft.Text(
                            "音乐库",
                            size=16,
                            weight=ft.FontWeight.W_700,
                            color=palette.TEXT_MAIN,
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            f"{len(tracks)} / {total_count} 首",
                            size=11,
                            color=palette.TEXT_MUTED,
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
                    border={
                        ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                            border_radius=12,
                            side=ft.BorderSide(1, palette.BORDER),
                        ),
                        ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                            border_radius=12,
                            side=ft.BorderSide(2, palette.PRIMARY_LIGHT),
                        ),
                    },
                    dense=True,
                    content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    bgcolor=palette.SURFACE,
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
        border=ft.Border(bottom=ft.BorderSide(1, palette.BORDER)),
    )

    if not tracks:
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.LIBRARY_MUSIC_OUTLINED, size=48, color=palette.TEXT_MUTED),
                    ft.Text(
                        "暂无歌曲", size=14, weight=ft.FontWeight.W_600, color=palette.TEXT_DIM
                    ),
                    ft.Text(
                        "点击右上角导入音乐文件夹",
                        size=12,
                        color=palette.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
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
        bgcolor=palette.SURFACE,
        border=ft.Border(right=ft.BorderSide(1, palette.BORDER)),
        expand=False,
    )
