from __future__ import annotations

from pathlib import Path

from cs_music_player.audio_player import Track
from cs_music_player.lrclib import _query_params, _tag_value, pick_best


def test_pick_best_prefers_exact_synced_match() -> None:
    records = [
        {"trackName": "晴天", "artistName": "周杰伦", "syncedLyrics": None, "instrumental": False},
        {
            "trackName": "晴天",
            "artistName": "周杰伦",
            "syncedLyrics": "[00:01.00] 晴天",
            "instrumental": False,
        },
        {"trackName": "其他歌", "artistName": "某人", "syncedLyrics": "[00:00.00] x", "instrumental": True},
    ]
    best = pick_best(records, "晴天", "周杰伦")
    assert best is records[1]


def test_pick_best_discards_instrumental_when_alternative_exists() -> None:
    records = [
        {"trackName": "晴天", "artistName": "周杰伦", "syncedLyrics": None, "instrumental": True},
        {"trackName": "晴天", "artistName": "周杰伦", "syncedLyrics": "[00:00.00] y", "instrumental": False},
    ]
    assert pick_best(records, "晴天", "周杰伦") is records[1]


def test_pick_best_empty_returns_none() -> None:
    assert pick_best([], "晴天", "周杰伦") is None


def test_query_params_falls_back_to_file_stem() -> None:
    track = Track(path=Path("周杰伦 - 晴天.mp3"), duration=240.0)
    params = _query_params(track)
    assert params["track_name"] == "周杰伦 - 晴天"
    assert params["duration"] == "240"
    assert "artist_name" not in params


def test_query_params_drops_out_of_range_duration() -> None:
    track = Track(path=Path("no-duration.mp3"), duration=0.0)
    params = _query_params(track)
    assert "duration" not in params


def test_tag_value_handles_frames_and_lists() -> None:
    class Frame:
        def __init__(self, text):
            self.text = text

    tags = {"TPE1": Frame(["周杰伦"]), "TIT2": Frame("晴天")}
    assert _tag_value(tags, "TPE1", "artist", "\xa9ART") == "周杰伦"
    assert _tag_value(tags, "TIT2", "title", "\xa9nam") == "晴天"
    assert _tag_value(tags, "TALB", "album") == ""
    assert _tag_value(None, "TPE1") == ""