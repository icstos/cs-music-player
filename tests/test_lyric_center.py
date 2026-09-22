from __future__ import annotations

from cs_music_player.constants import LYRIC_FONT_DEFAULT
from cs_music_player.ui import (
    _lyric_row_height,
    _lyric_window,
    _lyric_window_rows,
)


def test_row_height_leaves_room_for_two_lines() -> None:
    """行高要装得下「放大一号的当前行」折两行。"""
    assert _lyric_row_height(LYRIC_FONT_DEFAULT) > (LYRIC_FONT_DEFAULT + 3) * 2
    assert _lyric_row_height(24.0) > _lyric_row_height(15.0)


def test_window_rows_is_always_odd() -> None:
    row_height = _lyric_row_height(LYRIC_FONT_DEFAULT)
    for height in range(0, 900, 7):
        assert _lyric_window_rows(float(height), row_height) % 2 == 1


def test_window_rows_never_overflows_viewport() -> None:
    row_height = _lyric_row_height(LYRIC_FONT_DEFAULT)
    for height in (0.0, 57.5, 172.5, 200.0, 300.0, 723.4):
        rows = _lyric_window_rows(height, row_height)
        assert rows * row_height <= max(height, row_height)


def test_window_rows_degrade_to_single_row() -> None:
    assert _lyric_window_rows(0.0, 57.5) == 1
    assert _lyric_window_rows(57.5, 57.5) == 1
    assert _lyric_window_rows(120.0, 0.0) == 1


def test_window_centres_active_line() -> None:
    """无论高亮哪一行，它都必须落在窗口正中（首尾行同理）。"""
    for active in range(20):
        window = _lyric_window(active, 20, 5)
        assert len(window) == 5
        assert window[2] == active


def test_window_pads_out_of_range_with_placeholders() -> None:
    assert _lyric_window(0, 20, 5) == [None, None, 0, 1, 2]
    assert _lyric_window(19, 20, 5) == [17, 18, 19, None, None]
    # 尚无高亮行（歌曲尚未开始）时以第 0 行为焦点
    assert _lyric_window(-1, 20, 5) == [None, None, 0, 1, 2]


def test_window_keeps_short_lyrics_centred() -> None:
    assert _lyric_window(1, 3, 5) == [None, 0, 1, 2, None]
