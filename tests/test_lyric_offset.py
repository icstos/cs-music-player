from __future__ import annotations

import asyncio
from pathlib import Path

from cs_music_player.lyrics import LyricLine, current_line_index
from cs_music_player.store import load_lyric_offsets, save_lyric_offset


class _FakePrefs:
    def __init__(self) -> None:
        self._data: dict = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value) -> None:
        self._data[key] = value


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


def test_lyric_offset_roundtrip_and_reset() -> None:
    prefs = _FakePrefs()
    key = str(Path("C:/Music/song.mp3").resolve())

    async def flow() -> float:
        await save_lyric_offset(prefs, key, 0.5)
        assert (await load_lyric_offsets(prefs)).get(key) == 0.5
        await save_lyric_offset(prefs, key, 0.0)
        return (await load_lyric_offsets(prefs)).get(key, 0.0)

    assert asyncio.run(flow()) == 0.0


def test_lyric_offset_isolated_per_track() -> None:
    prefs = _FakePrefs()
    key_a = str(Path("C:/Music/a.mp3").resolve())
    key_b = str(Path("C:/Music/b.mp3").resolve())

    async def flow() -> dict:
        await save_lyric_offset(prefs, key_a, -0.2)
        return await load_lyric_offsets(prefs)

    assert asyncio.run(flow()) == {key_a: -0.2}


def test_lyric_offset_rejects_corrupt_data() -> None:
    prefs = _FakePrefs()
    prefs._data["lyric_offsets"] = "not-json{{"

    assert asyncio.run(load_lyric_offsets(prefs)) == {}
