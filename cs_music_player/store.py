"""用户数据持久化：收藏列表、最近打开的文件夹等。"""

from __future__ import annotations

from pathlib import Path

from .audio_player import Track

FAVORITES_KEY = "favorite_tracks"
RECENT_FOLDERS_KEY = "recent_folders"
MAX_RECENT_FOLDERS = 8


def track_key(path: Path) -> str:
    """曲目唯一标识（绝对路径）。"""
    return str(path.resolve())


async def load_favorites(prefs) -> set[str]:
    raw = await prefs.get(FAVORITES_KEY)
    return set(raw or [])


async def save_favorites(prefs, favorites: set[str]) -> None:
    await prefs.set(FAVORITES_KEY, sorted(favorites))


def apply_favorites(tracks: list[Track], favorites: set[str]) -> None:
    for track in tracks:
        track.favorite = track_key(track.path) in favorites


async def load_recent_folders(prefs) -> list[str]:
    """读取最近打开过的文件夹（绝对路径，最新的在前）。"""
    raw = await prefs.get(RECENT_FOLDERS_KEY)
    return list(raw or [])


async def save_recent_folders(prefs, folders: list[str]) -> None:
    await prefs.set(RECENT_FOLDERS_KEY, list(folders))


def push_recent_folder(folders: list[str], folder: str) -> list[str]:
    """将文件夹置顶并去重，限制最多 ``MAX_RECENT_FOLDERS`` 条。"""
    resolved = str(Path(folder).expanduser().resolve())
    normalized: list[str] = []
    seen: set[str] = set()
    for item in [resolved, *folders]:
        candidate = str(Path(item).expanduser().resolve())
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized[:MAX_RECENT_FOLDERS]
