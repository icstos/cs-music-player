"""歌词时间偏移：按曲目持久化、解析容错与高亮行计算。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cs_music_player.models import LyricLine, Track
from cs_music_player.service.lyrics import LyricsService, current_line_index

from fakes import FakeLyricsRepository, FakeLyricsProvider, FakePreferences


def make_service(prefs: FakePreferences) -> LyricsService:
    return LyricsService(FakeLyricsRepository(), FakeLyricsProvider(), prefs)


def test_offset_advance_highlights_line_earlier() -> None:
    lines = [
        LyricLine(time=10.0, text="A"),
        LyricLine(time=20.0, text="B"),
    ]
    # 无偏移：position 10.0 高亮 A
    assert current_line_index(lines, 10.0) == 0
    # 提前 1s：position 9.0 已高亮 A
    assert current_line_index(lines, 9.0, offset=1.0) == 0
    # 提前 1s：position 19.0 已高亮 B
    assert current_line_index(lines, 19.0, offset=1.0) == 1


def test_offset_delay_highlights_line_later() -> None:
    lines = [LyricLine(time=10.0, text="A")]
    # 延后 0.1s：position 10.0 时 A 尚未高亮
    assert current_line_index(lines, 10.0, offset=-0.1) == -1
    # 延后 0.1s：position 10.1 时高亮 A
    assert current_line_index(lines, 10.1, offset=-0.1) == 0


def test_plain_lyrics_always_highlight_first_line() -> None:
    lines = [LyricLine(time=0.0, text=f"line {i}") for i in range(5)]
    assert current_line_index(lines, 0.0) == 0
    assert current_line_index(lines, 999.0) == 0


def test_no_lyrics_returns_minus_one() -> None:
    assert current_line_index([], 5.0) == -1


def test_lyric_offset_roundtrip_and_reset() -> None:
    service = make_service(FakePreferences())
    track = Track(path=Path("C:/Music/song.mp3"))

    async def flow() -> float:
        await service.set_offset(track, 0.5)
        assert await service.offset_for(track) == 0.5
        await service.set_offset(track, 0.0)
        return await service.offset_for(track)

    assert asyncio.run(flow()) == 0.0


def test_lyric_offset_isolated_per_track() -> None:
    prefs = FakePreferences()
    service = make_service(prefs)
    track_a = Track(path=Path("C:/Music/a.mp3"))
    track_b = Track(path=Path("C:/Music/b.mp3"))

    async def flow() -> float:
        await service.set_offset(track_a, -0.2)
        return await service.offset_for(track_b)

    assert asyncio.run(flow()) == 0.0
    assert asyncio.run(service.offset_for(track_a)) == -0.2


def test_lyric_offset_rejects_corrupt_data() -> None:
    service = make_service(FakePreferences({"lyric_offsets": "not-json{{"}))

    async def flow() -> float:
        return await service.offset_for(Track(path=Path("a.mp3")))

    assert asyncio.run(flow()) == 0.0


def test_offset_for_missing_track_is_zero() -> None:
    assert asyncio.run(make_service(FakePreferences()).offset_for(None)) == 0.0
