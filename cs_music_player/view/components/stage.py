"""主舞台：封面、标题与歌词面板的组合。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ...models import LYRIC_FONT_DEFAULT, LyricLine, Track
from ..theme import palette
from .cover import _track_cover
from .lyric_settings import LyricSettingsEntry
from .lyrics import LyricsPanel

__all__ = ["MainStage"]


# ── 主舞台（封面 + 歌词） ── #


@ft.component
def MainStage(
    track: Track | None,
    is_playing: bool,
    lyrics: list[LyricLine],
    active_index: int,
    has_lyrics_file: bool,
    lyric_offset: float = 0.0,
    lyric_font: float = LYRIC_FONT_DEFAULT,
    on_adjust_lyric: Callable[[float], None] | None = None,
    on_adjust_font: Callable[[float], None] | None = None,
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
            color=ft.Colors.with_opacity(0.15, palette.TEXT_MAIN),
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
                        content=ft.Icon(ft.Icons.GRAPHIC_EQ, color=palette.ACCENT, size=20),
                        alignment=ft.Alignment(1, -1),
                        margin=ft.Margin.only(top=8, right=8),
                        bgcolor=palette.ACCENT_TINT_10,
                        border_radius=20,
                        padding=ft.Padding.all(6),
                    ),
                ],
            ),
        )

    track_path = str(track.path) if track is not None else ""
    lyrics_section = ft.Column(
        [
            (
                LyricSettingsEntry(
                    lyric_offset,
                    lyric_font,
                    track_path,
                    on_adjust_lyric,
                    on_adjust_font,
                )
                if has_lyrics_file
                and on_adjust_lyric is not None
                and on_adjust_font is not None
                else ft.Container()
            ),
            ft.Container(
                content=LyricsPanel(
                    lyrics,
                    active_index,
                    has_lyrics_file,
                    font_size=lyric_font,
                ),
                expand=True,
            ),
        ],
        spacing=0,
        expand=True,
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
                                color=palette.TEXT_MAIN,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                subtitle,
                                size=13,
                                color=palette.TEXT_DIM,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=ft.Padding.only(top=32, left=32, right=32, bottom=16),
                ),
                lyrics_section,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        ),
        expand=True,
        bgcolor=palette.BG,
    )
