"""用户数据持久化：收藏列表等。"""

from __future__ import annotations

from pathlib import Path

from .audio_player import Track

FAVORITES_KEY = "favorite_tracks"


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
