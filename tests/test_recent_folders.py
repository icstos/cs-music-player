from __future__ import annotations

from pathlib import Path

from cs_music_player.store import (
    MAX_RECENT_FOLDERS,
    normalize_folder_path,
    push_recent_folder,
    toggle_pinned_folder,
)


def test_push_recent_folder_moves_existing_item_to_front() -> None:
    folders = ["C:/Music/B", "C:/Music/A", "C:/Music/C"]
    updated = push_recent_folder(folders, "C:/Music/A")
    assert Path(updated[0]).name == "A"
    assert len(updated) == 3
    assert len(set(updated)) == 3


def test_push_recent_folder_trims_history() -> None:
    folders = [f"C:/Music/{i}" for i in range(MAX_RECENT_FOLDERS + 2)]
    updated = push_recent_folder(folders, "C:/Music/new")
    assert len(updated) == MAX_RECENT_FOLDERS
    assert Path(updated[0]).name == "new"


def test_normalize_folder_path_resolves_and_standardizes() -> None:
    assert normalize_folder_path("C:/Music/A") == normalize_folder_path(
        "C:\\Music\\A"
    )


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
