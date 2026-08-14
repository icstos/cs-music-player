from __future__ import annotations

import random
from pathlib import Path

from cs_music_player.audio_player import Player, PlayerCallbacks, Track
from cs_music_player.constants import MODE_LOOP_ONE, MODE_SEQUENCE, MODE_SHUFFLE


def make_player(n: int) -> Player:
    page = type("Page", (), {"services": [], "update": lambda: None})()
    cb = PlayerCallbacks(
        on_position=lambda v: None,
        on_duration=lambda v: None,
        on_play_state=lambda v: None,
        on_track_change=lambda i: None,
    )
    player = Player(cb, page)
    player.set_tracks([Track(path=Path(f"{i}.mp3")) for i in range(n)])
    return player


def test_manual_next_in_sequence_mode_cycles() -> None:
    p = make_player(3)
    p.mode = MODE_SEQUENCE
    p.current = 2
    assert p._next_index(auto=False) == 0
    p.current = 0
    assert p._next_index(auto=False) == 1


def test_auto_next_in_sequence_mode_stops_at_end() -> None:
    p = make_player(3)
    p.mode = MODE_SEQUENCE
    p.current = 2
    assert p._next_index(auto=True) is None
    p.current = 1
    assert p._next_index(auto=True) == 2


def test_manual_next_in_loop_one_mode_repeats_current() -> None:
    p = make_player(3)
    p.mode = MODE_LOOP_ONE
    p.current = 1
    assert p._next_index(auto=False) == 1
    assert p._next_index(auto=True) == 1


def test_manual_prev_in_loop_one_mode_repeats_current() -> None:
    p = make_player(3)
    p.mode = MODE_LOOP_ONE
    p.current = 1
    assert p._prev_index() == 1


def test_manual_next_in_shuffle_mode_avoids_current() -> None:
    p = make_player(5)
    p.mode = MODE_SHUFFLE
    p.current = 2
    random.seed(7)
    for _ in range(50):
        nxt = p._next_index(auto=False)
        assert nxt != p.current


def test_manual_prev_in_shuffle_mode_avoids_current() -> None:
    p = make_player(5)
    p.mode = MODE_SHUFFLE
    p.current = 2
    random.seed(9)
    for _ in range(50):
        nxt = p._prev_index()
        assert nxt != p.current


def test_manual_prev_in_sequence_mode_goes_backwards() -> None:
    p = make_player(3)
    p.mode = MODE_SEQUENCE
    p.current = 0
    assert p._prev_index() == 2
    p.current = 2
    assert p._prev_index() == 1