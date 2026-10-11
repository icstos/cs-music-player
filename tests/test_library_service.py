"""音乐库服务：目录扫描、检索过滤、收藏与文件夹历史。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from cs_music_player.models import Track
from cs_music_player.service.library import LibraryService, filter_tracks

from fakes import FakeLyricsRepository, FakeMetadata, FakePicker, FakePreferences


def make_service(**kwargs: Any) -> LibraryService:
    return LibraryService(
        kwargs.get("metadata") or FakeMetadata(),
        kwargs.get("repository") or FakeLyricsRepository(),
        kwargs.get("preferences") or FakePreferences(),
        kwargs.get("picker"),
    )


def _write_songs(folder: Path, names: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"x")


# ── 检索 / 筛选 ── #


def _tracks() -> list[Track]:
    return [
        Track(path=Path("a.mp3"), title="晴天", artist="周杰伦"),
        Track(path=Path("b.mp3"), title="夜曲", artist="周杰伦"),
        Track(path=Path("sub/c.mp3"), title="Yellow", artist="Coldplay"),
    ]


def test_filter_tracks_matches_title_artist_and_folder() -> None:
    tracks = _tracks()
    assert filter_tracks(tracks, "晴天") == [tracks[0]]
    assert filter_tracks(tracks, "周杰伦") == tracks[:2]
    assert filter_tracks(tracks, "sub") == [tracks[2]]
    assert filter_tracks(tracks, "COLDPLAY") == [tracks[2]]


def test_filter_tracks_favorites_only() -> None:
    tracks = _tracks()
    tracks[1].favorite = True
    assert filter_tracks(tracks, "", favorites_only=True) == [tracks[1]]
    assert filter_tracks(tracks, "夜", favorites_only=True) == [tracks[1]]
    assert filter_tracks(tracks, "晴", favorites_only=True) == []


def test_filter_tracks_empty_query_returns_everything() -> None:
    assert filter_tracks(_tracks(), "") == _tracks()


def test_filter_tracks_does_not_strip_whitespace() -> None:
    """回归：旧实现的搜索词不做 strip，纯空格应当是「匹配不到任何曲目」。"""
    assert filter_tracks(_tracks(), "   ") == []
    assert filter_tracks(_tracks(), " 晴天") == []


# ── 目录扫描 ── #


def test_load_directory_only_scans_the_top_level(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.FLAC", "cover.jpg", "notes.txt"])
    _write_songs(folder / "nested", ["c.mp3"])
    service = make_service()

    tracks = service.load_directory(folder)

    assert [t.path.name for t in tracks] == ["a.mp3", "b.FLAC"]
    assert [t.audio_format for t in tracks] == ["MP3", "FLAC"]


def test_load_directory_matches_sibling_lyrics_folder(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3"])
    lyrics_dir = folder / "lyrics"
    lyrics_dir.mkdir()
    lrc = lyrics_dir / "a.lrc"
    lrc.write_text("[00:01.00] hi", encoding="utf-8")
    repository = FakeLyricsRepository({lrc: []})
    service = make_service(repository=repository)

    (track,) = service.load_directory(folder)

    assert track.lyrics_path == lrc


def test_load_directory_on_missing_folder_is_empty(tmp_path: Path) -> None:
    assert make_service().load_directory(tmp_path / "nope") == []


def test_create_track_rejects_unsupported_format(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["notes.txt"])
    service = make_service()

    assert service.create_track(folder / "notes.txt") is None
    assert service.create_track(folder / "missing.mp3") is None


def test_create_track_fills_metadata(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3"])
    metadata = FakeMetadata(duration=42.0, artist="A", album="B", cover="data:image/png;base64,x")
    service = make_service(metadata=metadata)

    track = service.create_track(folder / "a.mp3")

    assert track is not None
    assert track.title == "a"
    assert track.duration == 42.0
    assert track.artist == "A"
    assert track.album == "B"
    assert track.cover_src == "data:image/png;base64,x"
    assert track.file_size > 0


# ── 启动路径解析 ── #


def test_resolve_startup_directory_imports_without_playing(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.mp3"])
    load = make_service().resolve_startup(folder)

    assert load is not None
    assert load.autoplay is False
    assert load.play_index == 0
    assert [t.title for t in load.tracks] == ["a", "b"]


def test_resolve_startup_file_selects_and_autoplays_it(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.mp3"])
    load = make_service().resolve_startup(folder / "b.mp3")

    assert load is not None
    assert load.autoplay is True
    assert load.tracks[load.play_index].title == "b"


def test_resolve_startup_file_outside_a_library_yields_one_track(tmp_path: Path) -> None:
    folder = tmp_path / "lonely"
    _write_songs(folder, ["only.mp3"])
    load = make_service().resolve_startup(folder / "only.mp3")

    assert load is not None
    assert load.autoplay is True
    assert len(load.tracks) == 1
    assert load.play_index == 0


def test_resolve_startup_missing_path_is_none(tmp_path: Path) -> None:
    assert make_service().resolve_startup(tmp_path / "nope.mp3") is None


# ── 目录选择 ── #


def test_choose_music_folder_returns_path(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3"])
    service = make_service(picker=FakePicker(str(folder)))

    assert asyncio.run(service.choose_music_folder()) == folder


def test_choose_music_folder_without_picker_is_none() -> None:
    assert asyncio.run(make_service().choose_music_folder()) is None

    service = make_service(picker=FakePicker(None))
    assert asyncio.run(service.choose_music_folder()) is None
