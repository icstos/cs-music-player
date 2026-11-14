"""主舞台：封面、曲目信息与歌词面板。"""

from __future__ import annotations

from collections.abc import Callable

from ui import (
    Animation,
    AnimationCurve,
    BoxShadow,
    Colors,
    Column,
    Container,
    Control,
    CrossAxisAlignment,
    FontWeight,
    Icon,
    Icons,
    Offset,
    Padding,
    Row,
    SPACE,
    Text,
    TextAlign,
    TextOverflow,
    component,
)

from ...models import LYRIC_FONT_DEFAULT, LyricLine, Track
from .. import tokens as t
from .cover import track_cover
from .format import _fmt_bitrate, _fmt_frequency
from .lyric_settings import LyricSettingsEntry
from .lyrics import LyricsPanel

__all__ = ["MainStage"]

#: 封面边长：横幅窗口里再大就会把歌词挤成一条缝。
COVER_SIZE = 220


@component
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
) -> Control:
    """上半屏是「这首歌是什么」，下半屏是「唱到哪一句」。

    歌词区独占剩余空间，并且**宽度限死**（``max_width``）：一行歌词横跨 1400px
    时眼睛要来回扫，读起来比换行更累。
    """
    title = "未选择歌曲" if track is None else track.title
    subtitle = "导入一个音乐文件夹开始" if track is None else (
        track.artist or track.path.parent.name
    )
    meta = _meta_line(track)

    heading = Column(
        controls=[
            Container(
                content=track_cover(
                    track,
                    size=COVER_SIZE,
                    is_playing=is_playing,
                    letter_fallback=True,
                ),
                shadow=BoxShadow(
                    spread_radius=0,
                    blur_radius=32,
                    color=Colors.with_opacity(0.18, Colors.SHADOW),
                    offset=Offset(0, 12),
                ),
                animate=Animation(300, AnimationCurve.EASE_OUT),
            ),
            Container(height=SPACE["2"]),
            Text(
                title,
                size=22,
                weight=FontWeight.W_700,
                color=t.TEXT,
                max_lines=1,
                overflow=TextOverflow.ELLIPSIS,
                text_align=TextAlign.CENTER,
            ),
            Text(
                subtitle,
                size=13,
                color=t.TEXT_SOFT,
                max_lines=1,
                overflow=TextOverflow.ELLIPSIS,
                text_align=TextAlign.CENTER,
            ),
            *([Text(meta, size=11, color=t.TEXT_SOFT)] if meta else []),
            _PlayState(is_playing=is_playing, has_track=track is not None),
        ],
        horizontal_alignment=CrossAxisAlignment.CENTER,
        spacing=SPACE["1"],
        tight=True,
    )

    lyrics_section = Column(
        controls=[
            (
                LyricSettingsEntry(
                    lyric_offset,
                    lyric_font,
                    str(track.path) if track is not None else "",
                    on_adjust_lyric,
                    on_adjust_font,
                )
                if has_lyrics_file
                and on_adjust_lyric is not None
                and on_adjust_font is not None
                else Container(height=SPACE["2"])
            ),
            Container(
                content=LyricsPanel(
                    lyrics,
                    active_index,
                    has_lyrics_file,
                    font_size=lyric_font,
                ),
                expand=True,
                # 限宽：一行歌词的长度控制在一屏能扫完的范围内
                width=760,
            ),
        ],
        spacing=0,
        expand=True,
        horizontal_alignment=CrossAxisAlignment.CENTER,
    )

    return Container(
        content=Column(
            controls=[
                Container(
                    content=heading,
                    padding=Padding.only(
                        top=SPACE["8"], left=SPACE["8"], right=SPACE["8"], bottom=SPACE["4"]
                    ),
                ),
                lyrics_section,
            ],
            horizontal_alignment=CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        ),
        expand=True,
        bgcolor=t.CANVAS,
    )


def _meta_line(track: Track | None) -> str:
    """技术参数一行（格式 · 采样率 · 码率）；缺哪项就少哪项，全缺则不显示。"""
    if track is None:
        return ""
    parts = [
        track.audio_format.upper() if track.audio_format else "",
        _fmt_frequency(track.sample_rate),
        _fmt_bitrate(track.bitrate),
    ]
    return " · ".join(part for part in parts if part)


@component
def _PlayState(*, is_playing: bool, has_track: bool) -> Control:
    """播放状态胶囊：有歌在放时出现，暂停 / 无歌时整行不占位。"""
    if not has_track:
        return Container(height=SPACE["4"])
    if not is_playing:
        return Container(height=SPACE["4"])
    return Container(
        content=Row(
            controls=[
                Icon(Icons.GRAPHIC_EQ, size=14, color=Colors.ON_PRIMARY),
                Text(
                    "正在播放",
                    size=11,
                    weight=FontWeight.W_600,
                    color=Colors.ON_PRIMARY,
                ),
            ],
            spacing=6,
            # 不 tight 的话 Row 会吃满整行宽度，胶囊就成了一条横贯整页的色带
            tight=True,
            vertical_alignment=CrossAxisAlignment.CENTER,
        ),
        padding=Padding.symmetric(horizontal=10, vertical=4),
        border_radius=999,
        bgcolor=Colors.PRIMARY,
    )
