"""用户数据持久化：收藏列表、最近打开的文件夹等。"""

from __future__ import annotations

from pathlib import Path

from .audio_player import Track

FAVORITES_KEY = "favorite_tracks"
RECENT_FOLDERS_KEY = "recent_folders"
PINNED_FOLDERS_KEY = "pinned_folders"
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


def normalize_folder_path(folder: str) -> str:
    """将文件夹路径标准化为绝对路径字符串。"""
    return str(Path(folder).expanduser().resolve())


def push_recent_folder(folders: list[str], folder: str) -> list[str]:
    """将文件夹置顶并去重，限制最多 ``MAX_RECENT_FOLDERS`` 条。"""
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


async def load_pinned_folders(prefs) -> set[str]:
    """读取固定（收藏）的文件夹路径集合。"""
    raw = await prefs.get(PINNED_FOLDERS_KEY)
    return set(raw or [])


async def save_pinned_folders(prefs, folders: set[str]) -> None:
    await prefs.set(PINNED_FOLDERS_KEY, sorted(folders))


def toggle_pinned_folder(folders: set[str], folder: str) -> set[str]:
    """切换某个文件夹的固定状态，返回新的固定集合。"""
    resolved = normalize_folder_path(folder)
    updated = {normalize_folder_path(f) for f in folders}
    if resolved in updated:
        updated.discard(resolved)
    else:
        updated.add(resolved)
    return updated
