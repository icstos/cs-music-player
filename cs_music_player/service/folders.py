"""文件夹历史服务：最近打开与固定（收藏）的文件夹。

与 :mod:`cs_music_player.service.library` 分开是单一职责的要求：那边管
「曲目」，这边管「文件夹历史」。
"""

from __future__ import annotations

from pathlib import Path

from ..infra.ports import (
    PINNED_FOLDERS_KEY,
    RECENT_FOLDERS_KEY,
    PreferencesPort,
)
from ..models import MAX_RECENT_FOLDERS

__all__ = [
    "FolderHistoryService",
    "normalize_folder_path",
    "push_recent_folder",
    "toggle_pinned_folder",
]


# ── 纯业务规则 ── #


def normalize_folder_path(folder: str) -> str:
    """将文件夹路径标准化为绝对路径字符串。"""
    return str(Path(folder).expanduser().resolve())


def push_recent_folder(folders: list[str], folder: str) -> list[str]:
    """将文件夹置顶并去重，限制最多 :data:`MAX_RECENT_FOLDERS` 条。"""
    resolved = normalize_folder_path(folder)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in [resolved, *folders]:
        candidate = normalize_folder_path(item)
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized[:MAX_RECENT_FOLDERS]


def toggle_pinned_folder(folders: set[str], folder: str) -> set[str]:
    """切换某个文件夹的固定状态，返回新的固定集合。"""
    resolved = normalize_folder_path(folder)
    updated = {normalize_folder_path(f) for f in folders}
    if resolved in updated:
        updated.discard(resolved)
    else:
        updated.add(resolved)
    return updated


# ── 服务 ── #


class FolderHistoryService:
    """最近打开 / 固定文件夹的读写与去重上限。

    Args:
        preferences: 持久化文件夹历史。
    """

    def __init__(self, preferences: PreferencesPort) -> None:
        self._prefs = preferences

    async def recent_folders(self) -> list[str]:
        """读取最近打开过的文件夹（绝对路径，最新的在前）。"""
        raw = await self._prefs.get(RECENT_FOLDERS_KEY)
        return list(raw or [])

    async def remember_folder(self, folder: str) -> list[str]:
        """把文件夹记入历史并返回最新列表。"""
        folders = push_recent_folder(await self.recent_folders(), folder)
        await self._prefs.set(RECENT_FOLDERS_KEY, list(folders))
        return folders

    async def clear_recent_folders(self) -> None:
        """清空最近打开记录（固定文件夹不受影响）。"""
        await self._prefs.set(RECENT_FOLDERS_KEY, [])

    async def pinned_folders(self) -> set[str]:
        """读取固定（收藏）的文件夹路径集合。"""
        raw = await self._prefs.get(PINNED_FOLDERS_KEY)
        return set(raw or [])

    async def toggle_pinned(self, folder: str) -> set[str]:
        """切换文件夹的固定状态并持久化，返回新的集合。"""
        pinned = toggle_pinned_folder(await self.pinned_folders(), folder)
        await self._prefs.set(PINNED_FOLDERS_KEY, sorted(pinned))
        return pinned
