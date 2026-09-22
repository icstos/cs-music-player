from __future__ import annotations

from cs_music_player.constants import (
    LYRIC_FONT_DEFAULT,
    LYRIC_FONT_MAX,
    LYRIC_FONT_MIN,
    LYRIC_LINE_FACTOR,
    LYRIC_ROW_GAP_RATIO,
)
from cs_music_player.ui import (
    _lyric_active_font_size,
    _lyric_active_pad,
    _lyric_active_row_height,
    _lyric_row_height,
    _lyric_window,
    _lyric_window_rows,
)

SIZES = (LYRIC_FONT_MIN, LYRIC_FONT_DEFAULT, LYRIC_FONT_MAX)


def test_row_height_is_font_line_plus_breathing_room() -> None:
    """普通行高 = 字号 × (1.4 单行高度 + 0.6 呼吸空间)。"""
    for size in SIZES:
        assert _lyric_row_height(size) == round(
            size * (LYRIC_LINE_FACTOR + LYRIC_ROW_GAP_RATIO), 1
        )
    assert _lyric_row_height(LYRIC_FONT_DEFAULT) == 30.0
    assert _lyric_row_height(24.0) == 48.0
    assert _lyric_row_height(24.0) > _lyric_row_height(15.0)


def test_row_height_is_tighter_than_two_line_reservation() -> None:
    """回归：不再为「每行都可能折两行」预留高度（旧版 2.9×字号+14 = 57.5）。"""
    old = 2.9 * LYRIC_FONT_DEFAULT + 14.0
    assert _lyric_row_height(LYRIC_FONT_DEFAULT) <= old * 0.6


def test_row_height_fits_one_line_with_visible_gap() -> None:
    """普通行装得下一行文本，且留出的空白不小于半个字号。"""
    for size in SIZES:
        assert _lyric_row_height(size) > size * LYRIC_LINE_FACTOR
        assert _lyric_row_height(size) - size * LYRIC_LINE_FACTOR >= size * 0.5


def test_active_row_fits_two_lines_of_enlarged_text() -> None:
    """放大后的当前行折两行也不会被裁——那是它自适应高度的上限。"""
    for size in SIZES:
        assert _lyric_active_row_height(size) >= (
            2 * _lyric_active_font_size(size) * LYRIC_LINE_FACTOR
        )
        assert _lyric_active_row_height(size) > _lyric_row_height(size)


def test_active_line_without_wrap_is_as_tall_as_normal_row() -> None:
    """当前行没折行时（含上下留白）与普通行等高，行距才均匀。"""
    for size in SIZES:
        one_line = (
            _lyric_active_font_size(size) * LYRIC_LINE_FACTOR
            + _lyric_active_pad(size) * 2
        )
        assert abs(one_line - _lyric_row_height(size)) <= 0.2


def test_window_rows_is_always_odd() -> None:
    row = _lyric_row_height(LYRIC_FONT_DEFAULT)
    active = _lyric_active_row_height(LYRIC_FONT_DEFAULT)
    for height in range(0, 900, 7):
        assert _lyric_window_rows(float(height), row, active) % 2 == 1


def test_window_never_overflows_viewport_even_if_active_wraps() -> None:
    """整组高度（含可能折两行的当前行）不超出歌词区。"""
    row = _lyric_row_height(LYRIC_FONT_DEFAULT)
    active = _lyric_active_row_height(LYRIC_FONT_DEFAULT)
    for height in (0.0, 30.0, 57.5, 90.0, 200.0, 300.0, 723.4, 783.4):
        rows = _lyric_window_rows(height, row, active)
        assert (rows - 1) * row + active <= max(height, active)


def test_window_rows_degrade_to_single_row() -> None:
    row = _lyric_row_height(LYRIC_FONT_DEFAULT)
    active = _lyric_active_row_height(LYRIC_FONT_DEFAULT)
    assert _lyric_window_rows(0.0, row, active) == 1
    assert _lyric_window_rows(active, row, active) == 1
    assert _lyric_window_rows(120.0, 0.0, active) == 1


def test_window_holds_more_lines_than_before() -> None:
    """同样的歌词区，紧凑行距下可见行数明显更多。"""
    row = _lyric_row_height(LYRIC_FONT_DEFAULT)
    active = _lyric_active_row_height(LYRIC_FONT_DEFAULT)
    old_row = 2.9 * LYRIC_FONT_DEFAULT + 14.0
    viewport = 783.4
    now = _lyric_window_rows(viewport, row, active)
    before = _lyric_window_rows(viewport, old_row, old_row)
    assert now > before * 1.6


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
