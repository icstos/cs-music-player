"""歌词字号（全局设置）：默认值、范围校验与往返持久化。"""

from __future__ import annotations

import asyncio

from cs_music_player.models import LYRIC_FONT_DEFAULT, LYRIC_FONT_MAX, LYRIC_FONT_MIN
from cs_music_player.service.settings import SettingsService

from fakes import FakePreferences


def test_lyric_font_roundtrip() -> None:
    service = SettingsService(FakePreferences())

    async def flow() -> float:
        await service.save_lyric_font(19.0)
        return await service.lyric_font()

    assert asyncio.run(flow()) == 19.0


def test_lyric_font_default_when_missing() -> None:
    assert asyncio.run(SettingsService(FakePreferences()).lyric_font()) == (
        LYRIC_FONT_DEFAULT
    )


def test_lyric_font_rejects_out_of_range() -> None:
    service = SettingsService(FakePreferences({"lyric_font": 99.0}))
    assert asyncio.run(service.lyric_font()) == LYRIC_FONT_DEFAULT
    service = SettingsService(FakePreferences({"lyric_font": 1.0}))
    assert asyncio.run(service.lyric_font()) == LYRIC_FONT_DEFAULT


def test_lyric_font_rejects_corrupt_data() -> None:
    service = SettingsService(FakePreferences({"lyric_font": "not-a-number"}))
    assert asyncio.run(service.lyric_font()) == LYRIC_FONT_DEFAULT


def test_lyric_font_is_clamped_when_saved() -> None:
    prefs = FakePreferences()
    service = SettingsService(prefs)

    async def flow() -> float:
        await service.save_lyric_font(99.0)
        return await service.lyric_font()

    assert asyncio.run(flow()) == LYRIC_FONT_MAX


def test_lyric_font_default_within_range() -> None:
    assert LYRIC_FONT_MIN <= LYRIC_FONT_DEFAULT <= LYRIC_FONT_MAX
