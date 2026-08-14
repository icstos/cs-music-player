from __future__ import annotations

from pathlib import Path

from cs_music_player.store import MAX_RECENT_FOLDERS, push_recent_folder


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
