"""歌词面板与歌词行组件。"""

from __future__ import annotations

import flet as ft

from ...models import (
    LYRIC_ACTIVE_DELTA,
    LYRIC_FONT_DEFAULT,
    LYRIC_LINE_FACTOR,
    LYRIC_ROW_GAP_RATIO,
    LyricLine,
)
from ..theme import palette

__all__ = ["LyricsLine", "LyricsPanel"]


# ── 歌词面板 ── #


def _lyric_active_font_size(font_size: float) -> float:
    """正在播放的行的字号（比普通行大一号）。"""
    return font_size + LYRIC_ACTIVE_DELTA


def _lyric_row_height(font_size: float) -> float:
    """普通歌词行的高度：一行文本的天然高度 + 行间留白（字号 × 2）。"""
    return round(font_size * (LYRIC_LINE_FACTOR + LYRIC_ROW_GAP_RATIO), 1)


def _lyric_active_pad(font_size: float) -> float:
    """当前行的上下留白：让「放大后只占一行」的当前行与普通行等高。"""
    line_height = _lyric_active_font_size(font_size) * LYRIC_LINE_FACTOR
    return max(0.0, round((_lyric_row_height(font_size) - line_height) / 2, 1))


def _lyric_active_row_height(font_size: float) -> float:
    """当前行的最大高度：放大后的当前行折两行时的高度（含上下留白）。

    当前行按内容自适应高度（折行才不会被裁），这里给的是它可能达到的上限，
    用来为「窗口行数」预留余量。
    """
    line_height = _lyric_active_font_size(font_size) * LYRIC_LINE_FACTOR
    return round(line_height * 2 + _lyric_active_pad(font_size) * 2, 1)


def _lyric_window_rows(
    viewport_height: float,
    row_height: float,
    active_row_height: float = 0.0,
) -> int:
    """歌词区能容纳的行数，恒取奇数——偶数行会让当前行偏离中线半行。

    当前行可能因折行而比普通行高，先扣掉这段余量，避免整组溢出歌词区。
    """
    if row_height <= 0:
        return 1
    spare = max(0.0, active_row_height - row_height)
    rows = int(max(0.0, viewport_height - spare) // row_height)
    if rows % 2 == 0:
        rows -= 1
    return max(1, rows)


def _lyric_window(active: int, total: int, rows: int) -> list[int | None]:
    """以当前行为中心的歌词窗口，``None`` 是越界处的空白占位行。

    窗口行数固定为奇数、当前行置于正中，开头/结尾的歌词便同样停在区域中线上。
    """
    half = (rows - 1) // 2
    focus = active if active >= 0 else 0
    return [
        index if 0 <= index < total else None
        for index in range(focus - half, focus + half + 1)
    ]


@ft.component
def LyricsLine(
    text: str,
    is_current: bool,
    font_size: float = LYRIC_FONT_DEFAULT,
    row_height: float = 0.0,
) -> ft.Control:
    """一行歌词。

    普通行固定为一行高（``row_height``，超出以 ``…`` 收尾）；当前行放大一号
    并按内容自适应高度（最多两行），因此折行不会被裁——它多出来的那点高度由
    上下留白补齐，没折行时恰好与普通行等高。
    """
    if is_current:
        size = _lyric_active_font_size(font_size)
        pad = _lyric_active_pad(font_size)
        height, max_lines = None, 2
    else:
        size = font_size
        pad = 0.0
        height, max_lines = row_height or None, 1
    return ft.Container(
        content=ft.Text(
            text,
            size=size,
            weight=ft.FontWeight.W_700 if is_current else ft.FontWeight.NORMAL,
            color=palette.PRIMARY if is_current else palette.TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
            max_lines=max_lines,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        height=height,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=28, vertical=pad),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


@ft.component
def LyricsPanel(
    lines: list[LyricLine],
    active_index: int,
    has_lyrics_file: bool,
    font_size: float = LYRIC_FONT_DEFAULT,
) -> ft.Control:
    """歌词面板：正在播放的那一行始终停在歌词区垂直中线上。

    只渲染「当前行 ± 半屏」的窗口并按中线排布，所以首尾歌词也能居中；
    普通行等高（因而当前行上下两半的行数相等，居中才精确），窗口行数由歌词区
    实测高度推算（``on_size_change``），随窗口尺寸与字号自适应。

    当前高亮行索引由视图模型作为派生状态传入（声明式：UI = f(state)）。
    """
    viewport_height, set_viewport_height = ft.use_state(0.0)

    active = active_index
    row_height = _lyric_row_height(font_size)
    window = _lyric_window(
        active,
        len(lines),
        _lyric_window_rows(
            viewport_height,
            row_height,
            _lyric_active_row_height(font_size),
        ),
    )

    if not has_lyrics_file:
        body: ft.Control = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=36, color=palette.TEXT_MUTED),
                    ft.Text("暂无歌词", size=13, color=palette.TEXT_DIM),
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
            content=ft.Text("歌词文件无法解析", size=13, color=palette.TEXT_DIM),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        body = ft.Column(
            controls=[
                (
                    LyricsLine(lines[index].text, index == active, font_size, row_height)
                    if index is not None
                    else ft.Container(height=row_height)
                )
                for index in window
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )

    def on_size_change(e: ft.LayoutSizeChangeEvent) -> None:
        """记录歌词区实测高度，用以推算窗口行数。"""
        if abs(e.height - viewport_height) > 0.5:
            set_viewport_height(e.height)

    return ft.Container(
        content=body,
        expand=True,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        on_size_change=on_size_change,
    )
