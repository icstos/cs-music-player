"""Provider-level test: the LRCLIB client really uses tag text and writes the file."""
from __future__ import annotations

import asyncio
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cs_music_player.infra.lyrics_provider import LrclibLyricsProvider
from cs_music_player.models import AudioMetadata, TagText, Track


class _Metadata:
    def __init__(self, tags: TagText) -> None:
        self.tags = tags
        self.calls: list[Path] = []

    def read(self, path: Path) -> AudioMetadata:
        return AudioMetadata()

    def cover_data_uri(self, path: Path) -> str | None:
        return None

    def read_tag_text(self, path: Path) -> TagText:
        self.calls.append(path)
        return self.tags


def _make(
    tmp_path: Path, *, tags: TagText, payload: Callable[[str], Any]
) -> tuple[LrclibLyricsProvider, Track, list[str]]:
    seen: list[str] = []

    def get_json(url: str) -> Any:
        seen.append(url)
        return payload(url)

    provider = LrclibLyricsProvider(_Metadata(tags), interval=0.0, get_json=get_json)
    track = Track(path=tmp_path / "世界三大禁曲之一 忏魂曲.mp3", duration=200.0)
    return provider, track, seen


def test_download_queries_with_tag_text_and_saves_synced_lyrics(tmp_path: Path) -> None:
    payload = {
        "id": 1,
        "trackName": "Room Of Angel",
        "artistName": "Akira Yamaoka",
        "syncedLyrics": "[00:01.00] hello",
        "instrumental": False,
    }
    provider, track, seen = _make(
        tmp_path, tags=TagText(title="Room Of Angel", artist="Akira Yamaoka"), payload=lambda url: payload
    )

    target = asyncio.run(provider.download(track))

    assert target == tmp_path / "lyrics" / "世界三大禁曲之一 忏魂曲.lrc"
    assert target.read_text(encoding="utf-8") == "[00:01.00] hello\n"
    query = urllib.parse.parse_qs(urllib.parse.urlparse(seen[0]).query)
    assert query["track_name"] == ["Room Of Angel"]
    assert query["artist_name"] == ["Akira Yamaoka"]


def test_download_writes_plain_lyrics_as_txt(tmp_path: Path) -> None:
    """只有纯文本歌词时保存为 .txt（LRCLIB 的 /get 只认带时间轴的命中）。"""
    plain = {
        "id": 2,
        "trackName": "x",
        "artistName": "",
        "syncedLyrics": None,
        "plainLyrics": "line one\nline two",
        "instrumental": False,
    }

    def payload(url: str) -> Any:
        return None if "/get?" in url else [plain]

    provider, track, _ = _make(tmp_path, tags=TagText(), payload=payload)

    target = asyncio.run(provider.download(track))

    assert target is not None
    assert target.suffix == ".txt"
    assert target.read_text(encoding="utf-8") == "line one\nline two\n"


def test_download_falls_back_to_search_when_get_misses(tmp_path: Path) -> None:
    search_hit = {
        "id": 3,
        "trackName": "Room Of Angel",
        "artistName": "Akira Yamaoka",
        "syncedLyrics": "[00:02.00] found by search",
        "instrumental": False,
    }

    def payload(url: str) -> Any:
        return None if "/get?" in url else [search_hit]

    provider, track, seen = _make(
        tmp_path, tags=TagText(title="Room Of Angel", artist="Akira Yamaoka"), payload=payload
    )

    target = asyncio.run(provider.download(track))

    assert target is not None
    assert "found by search" in target.read_text(encoding="utf-8")
    assert any("/search?" in url for url in seen)


def test_download_returns_none_when_nothing_is_found(tmp_path: Path) -> None:
    provider, track, _ = _make(tmp_path, tags=TagText(), payload=lambda url: None)

    assert asyncio.run(provider.download(track)) is None
    assert not (tmp_path / "lyrics").exists()


def test_download_returns_none_for_an_instrumental_record(tmp_path: Path) -> None:
    payload = {"id": 4, "trackName": "x", "instrumental": True, "syncedLyrics": "", "plainLyrics": ""}
    provider, track, _ = _make(tmp_path, tags=TagText(), payload=lambda url: payload)

    assert asyncio.run(provider.download(track)) is None
