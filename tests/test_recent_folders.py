"""最近文件夹 / 固定文件夹：标准化、去重、置顶与上限。"""

from __future__ import annotations

import asyncio

from cs_music_player.models import MAX_RECENT_FOLDERS
from cs_music_player.service.folders import (
    FolderHistoryService,
    normalize_folder_path,
    push_recent_folder,
    toggle_pinned_folder,
)

from fakes import FakePreferences


def make_service(prefs: FakePreferences) -> FolderHistoryService:
    return FolderHistoryService(prefs)


def test_push_recent_folder_moves_existing_item_to_front() -> None:
    folders = ["C:/Music/B", "C:/Music/A", "C:/Music/C"]
    updated = push_recent_folder(folders, "C:/Music/A")
    assert len(updated) == 3
    assert len(set(updated)) == 3
    assert updated[0] == normalize_folder_path("C:/Music/A")


def test_push_recent_folder_trims_history() -> None:
    folders = [f"C:/Music/{i}" for i in range(MAX_RECENT_FOLDERS + 2)]
    updated = push_recent_folder(folders, "C:/Music/new")
    assert len(updated) == MAX_RECENT_FOLDERS
    assert updated[0].endswith("new")


def test_normalize_folder_path_resolves_and_standardizes() -> None:
    assert normalize_folder_path("C:/Music/A") == normalize_folder_path("C:\\Music\\A")


def test_toggle_pinned_folder_adds_and_removes() -> None:
    pinned = set()
    pinned = toggle_pinned_folder(pinned, "C:/Music/A")
    assert pinned == {normalize_folder_path("C:/Music/A")}
    pinned = toggle_pinned_folder(pinned, "C:/Music/A")
    assert pinned == set()


def test_toggle_pinned_folder_deduplicates_variants() -> None:
    pinned = {normalize_folder_path("C:/Music/A")}
    pinned = toggle_pinned_folder(pinned, "C:\\Music\\A")
    assert pinned == set()


def test_recent_folder_roundtrip_through_service() -> None:
    prefs = FakePreferences()
    service = make_service(prefs)

    async def flow() -> list[str]:
        folders = await service.remember_folder("C:/Music/A")
        return folders

    assert asyncio.run(flow()) == [normalize_folder_path("C:/Music/A")]
    assert asyncio.run(service.recent_folders()) == [
        normalize_folder_path("C:/Music/A")
    ]


def test_clear_recent_folders_keeps_pinned() -> None:
    prefs = FakePreferences()
    service = make_service(prefs)

    async def flow() -> tuple[list[str], set[str]]:
        await service.remember_folder("C:/Music/A")
        await service.toggle_pinned("C:/Music/A")
        await service.clear_recent_folders()
        return await service.recent_folders(), await service.pinned_folders()

    recent, pinned = asyncio.run(flow())
    assert recent == []
    assert pinned == {normalize_folder_path("C:/Music/A")}


def test_theme_mode_roundtrip() -> None:
    from cs_music_player.models import ThemeMode
    from cs_music_player.service.settings import SettingsService

    service = SettingsService(FakePreferences())

    async def flow() -> ThemeMode:
        await service.save_theme_mode(ThemeMode.DARK)
        return await service.theme_mode()

    assert asyncio.run(flow()) == ThemeMode.DARK


def test_theme_mode_rejects_unknown_values() -> None:
    from cs_music_player.models import ThemeMode
    from cs_music_player.service.settings import SettingsService

    prefs = FakePreferences()

    async def flow() -> ThemeMode:
        await prefs.set("theme_mode", "neon")
        return await SettingsService(prefs).theme_mode()

    assert asyncio.run(flow()) == ThemeMode.SYSTEM


def test_color_theme_roundtrip_and_fallback() -> None:
    from cs_music_player.models import DEFAULT_COLOR_THEME, ColorTheme
    from cs_music_player.service.settings import SettingsService

    prefs = FakePreferences()
    service = SettingsService(prefs)

    async def flow() -> tuple[ColorTheme, ColorTheme, ColorTheme]:
        fresh = await service.color_theme()  # 没存过 → 默认配色
        await service.save_color_theme(ColorTheme.MINT)
        saved = await service.color_theme()
        await prefs.set("color_theme", "neon")  # 未知标识 → 回退默认
        broken = await service.color_theme()
        return fresh, saved, broken

    fresh, saved, broken = asyncio.run(flow())
    assert fresh == DEFAULT_COLOR_THEME
    assert saved == ColorTheme.MINT
    assert broken == DEFAULT_COLOR_THEME
    assert prefs.data["color_theme"] == "neon"
