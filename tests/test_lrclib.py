"""LRCLIB 查询参数与候选记录打分（纯函数，离线）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cs_music_player.infra.lyrics_provider import (
    detect_hanzi_style,
    pick_best,
    query_params,
)
from cs_music_player.infra.metadata import _first_tag_value, _tag_value
from cs_music_player.models import TagText, Track


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


def test_pick_best_prefers_simplified_over_traditional() -> None:
    """同一首歌存在简繁两个版本时，应优先选择简体。"""
    simplified = {
        "trackName": "晴天",
        "artistName": "周杰伦",
        "syncedLyrics": "[00:00.00] 晴天\n[00:01.00] 刮风这天我试过握着你手",
        "instrumental": False,
    }
    traditional = {
        "trackName": "晴天",
        "artistName": "周杰伦",
        "syncedLyrics": "[00:00.00] 晴天\n[00:01.00] 颳風這天我試過握著妳手",
        "instrumental": False,
    }
    assert pick_best([traditional, simplified], "晴天", "周杰伦") is simplified
    assert pick_best([simplified, traditional], "晴天", "周杰伦") is simplified


def test_pick_best_prefers_simplified_even_when_traditional_matches_duration() -> None:
    simplified = {
        "trackName": "晴天",
        "artistName": "周杰伦",
        "duration": 270,
        "syncedLyrics": "[00:00.00] 晴天\n[00:01.00] 刮风这天我试过握着你手",
        "instrumental": False,
    }
    traditional = {
        "trackName": "晴天",
        "artistName": "周杰伦",
        "duration": 269,
        "syncedLyrics": "[00:00.00] 晴天\n[00:01.00] 颳風這天我試過握著妳手",
        "instrumental": False,
    }
    assert pick_best([traditional, simplified], "晴天", "周杰伦", 269) is simplified


def test_pick_best_empty_returns_none() -> None:
    assert pick_best([], "晴天", "周杰伦") is None


def test_detect_hanzi_style() -> None:
    assert detect_hanzi_style("刮风这天我试过握着你手") == "simplified"
    assert detect_hanzi_style("颳風這天我試過握著妳手") == "traditional"
    assert detect_hanzi_style("[00:01.00]") is None
    assert detect_hanzi_style("") is None
    assert detect_hanzi_style("something without hanzi") is None


def test_query_params_falls_back_to_file_stem() -> None:
    track = Track(path=Path("周杰伦 - 晴天.mp3"), duration=240.0)
    params = query_params(track)
    assert params["track_name"] == "周杰伦 - 晴天"
    assert params["duration"] == "240"
    assert "artist_name" not in params


def test_query_params_prefers_embedded_tags() -> None:
    """回归：检索用的是音频标签原文，没有标签才回退到文件名。"""
    track = Track(path=Path("世界三大禁曲之一 忏魂曲.mp3"), duration=270.4)
    tags = TagText(title="Room Of Angel", artist="Akira Yamaoka", album="Silent Hill 4")
    params = query_params(track, tags)
    assert params == {
        "track_name": "Room Of Angel",
        "artist_name": "Akira Yamaoka",
        "album_name": "Silent Hill 4",
        "duration": "270",
    }


def test_query_params_falls_back_when_tags_are_missing() -> None:
    track = Track(path=Path("track.mp3"), duration=100.0)
    assert query_params(track, TagText())["track_name"] == "track"


def test_first_tag_value_returns_single_value_not_joined() -> None:
    """多值标签取首值（与界面展示用的「A / B」拼接区分开）。"""
    class Frame:
        def __init__(self, text: Any) -> None:
            self.text = text

    tags = {"TPE1": Frame(["A", "B"]), "TIT2": Frame("Solo")}
    assert _first_tag_value(tags, "TPE1") == "A"
    assert _first_tag_value(tags, "TIT2") == "Solo"
    assert _first_tag_value(tags, "TALB") == ""
    assert _first_tag_value(None, "TPE1") == ""


def test_query_params_drops_out_of_range_duration() -> None:
    track = Track(path=Path("no-duration.mp3"), duration=0.0)
    params = query_params(track)
    assert "duration" not in params


def test_tag_value_handles_frames_and_lists() -> None:
    class Frame:
        def __init__(self, text: Any) -> None:
            self.text = text

    tags = {"TPE1": Frame(["周杰伦"]), "TIT2": Frame("晴天")}
    assert _tag_value(tags, "TPE1", "artist", "\xa9ART") == "周杰伦"
    assert _tag_value(tags, "TIT2", "title", "\xa9nam") == "晴天"
    assert _tag_value(tags, "TALB", "album") == ""
    assert _tag_value(None, "TPE1") == ""


def test_tag_value_joins_multiple_values_and_prefers_key_order() -> None:
    class Frame:
        def __init__(self, text: Any) -> None:
            self.text = text

    # 多值标签按原实现用 " / " 连接；候选键按顺序取第一个非空的
    assert _tag_value({"TPE1": Frame(["A", "B"])}, "TPE1") == "A / B"
    assert _tag_value({"artist": "C", "TPE1": Frame(["A"])}, "TPE1", "artist") == "A"
    assert _tag_value({"artist": "C"}, "TPE1", "artist") == "C"
