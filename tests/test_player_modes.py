"""播放模式策略：下一首 / 上一首是谁（纯函数，无 IO）。"""

from __future__ import annotations

import random

from cs_music_player.models import MODE_LOOP_ONE, MODE_SEQUENCE, MODE_SHUFFLE
from cs_music_player.service.playback import next_index, prev_index


def test_manual_next_in_sequence_mode_cycles() -> None:
    assert next_index(MODE_SEQUENCE, 2, 3) == 0
    assert next_index(MODE_SEQUENCE, 0, 3) == 1


def test_auto_next_in_sequence_mode_stops_at_end() -> None:
    assert next_index(MODE_SEQUENCE, 2, 3, auto=True) is None
    assert next_index(MODE_SEQUENCE, 1, 3, auto=True) == 2


def test_manual_next_in_loop_one_mode_repeats_current() -> None:
    assert next_index(MODE_LOOP_ONE, 1, 3) == 1
    assert next_index(MODE_LOOP_ONE, 1, 3, auto=True) == 1


def test_manual_prev_in_loop_one_mode_repeats_current() -> None:
    assert prev_index(MODE_LOOP_ONE, 1, 3) == 1


def test_manual_next_in_shuffle_mode_avoids_current() -> None:
    random.seed(7)
    for _ in range(50):
        assert next_index(MODE_SHUFFLE, 2, 5) != 2


def test_manual_prev_in_shuffle_mode_avoids_current() -> None:
    random.seed(9)
    for _ in range(50):
        assert prev_index(MODE_SHUFFLE, 2, 5) != 2


def test_manual_prev_in_sequence_mode_goes_backwards() -> None:
    assert prev_index(MODE_SEQUENCE, 0, 3) == 2
    assert prev_index(MODE_SEQUENCE, 2, 3) == 1


def test_empty_list_has_no_neighbours() -> None:
    assert next_index(MODE_SEQUENCE, 0, 0) is None
    assert prev_index(MODE_SEQUENCE, 0, 0) is None


def test_single_track_shuffle_stays_on_it() -> None:
    assert next_index(MODE_SHUFFLE, 0, 1) == 0
    assert prev_index(MODE_SHUFFLE, 0, 1) == 0


def test_next_index_with_no_current_starts_at_first() -> None:
    assert next_index(MODE_SEQUENCE, -1, 3) == 0


def test_play_mode_values_are_stable_labels() -> None:
    """模式取值即界面文案（tooltip / 持久化标识），改动会让文案漂移。"""
    assert str(MODE_SEQUENCE) == "顺序播放"
    assert str(MODE_LOOP_ONE) == "单曲循环"
    assert str(MODE_SHUFFLE) == "随机播放"
