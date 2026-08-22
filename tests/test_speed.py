from __future__ import annotations

from pathlib import Path

from cs_music_player.audio_player import Player, PlayerCallbacks, Track
from cs_music_player.constants import SPEED_MAX, SPEED_MIN, SPEED_PRESETS


def make_player() -> Player:
    page = type("Page", (), {"services": [], "update": lambda: None})()
    cb = PlayerCallbacks(
        on_position=lambda v: None,
        on_duration=lambda v: None,
        on_play_state=lambda v: None,
        on_track_change=lambda i: None,
    )
    player = Player(cb, page)
    player.set_tracks([Track(path=Path("a.mp3"))])
    return player


def test_default_speed_is_normal() -> None:
    p = make_player()
    assert p._speed == 1.0
    assert p._new_audio("a.mp3").playback_rate == 1.0


def test_set_speed_applies_to_new_audio() -> None:
    p = make_player()
    p.set_speed(1.5)
    assert p._speed == 1.5
    assert p._new_audio("a.mp3").playback_rate == 1.5


def test_set_speed_clamps_to_range() -> None:
    p = make_player()
    p.set_speed(99.0)
    assert p._speed == SPEED_MAX
    p.set_speed(0.01)
    assert p._speed == SPEED_MIN


def test_speed_presets_are_within_range() -> None:
    assert all(SPEED_MIN <= r <= SPEED_MAX for r in SPEED_PRESETS)
    assert 1.0 in SPEED_PRESETS
