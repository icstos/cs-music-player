from __future__ import annotations

import asyncio

from cs_music_player.constants import LYRIC_FONT_DEFAULT, LYRIC_FONT_MAX, LYRIC_FONT_MIN
from cs_music_player.store import load_lyric_font, save_lyric_font


class _FakePrefs:
    def __init__(self) -> None:
        self._data: dict = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value) -> None:
        self._data[key] = value


def test_lyric_font_roundtrip() -> None:
    prefs = _FakePrefs()

    async def flow() -> float:
        await save_lyric_font(prefs, 19.0)
        return await load_lyric_font(prefs)

    assert asyncio.run(flow()) == 19.0


def test_lyric_font_default_when_missing() -> None:
    prefs = _FakePrefs()
    assert asyncio.run(load_lyric_font(prefs)) == LYRIC_FONT_DEFAULT


def test_lyric_font_rejects_out_of_range() -> None:
    prefs = _FakePrefs()
    prefs._data["lyric_font"] = 99.0
    assert asyncio.run(load_lyric_font(prefs)) == LYRIC_FONT_DEFAULT
    prefs._data["lyric_font"] = 1.0
    assert asyncio.run(load_lyric_font(prefs)) == LYRIC_FONT_DEFAULT


def test_lyric_font_rejects_corrupt_data() -> None:
    prefs = _FakePrefs()
    prefs._data["lyric_font"] = "not-a-number"
    assert asyncio.run(load_lyric_font(prefs)) == LYRIC_FONT_DEFAULT


def test_lyric_font_default_within_range() -> None:
    assert LYRIC_FONT_MIN <= LYRIC_FONT_DEFAULT <= LYRIC_FONT_MAX
