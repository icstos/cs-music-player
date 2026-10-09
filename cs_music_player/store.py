"""用户数据持久化：收藏列表、最近打开的文件夹、歌词微调偏移等。"""

from __future__ import annotations

import json
from pathlib import Path

from .audio_player import Track
from .constants import (
    DESKTOP_LYRIC_FONT_DEFAULT,
    DESKTOP_LYRIC_FONT_MAX,
    DESKTOP_LYRIC_FONT_MIN,
    LYRIC_FONT_DEFAULT,
    LYRIC_FONT_MAX,
    LYRIC_FONT_MIN,
)

FAVORITES_KEY = "favorite_tracks"
RECENT_FOLDERS_KEY = "recent_folders"
PINNED_FOLDERS_KEY = "pinned_folders"
THEME_MODE_KEY = "theme_mode"
LYRIC_OFFSETS_KEY = "lyric_offsets"
LYRIC_FONT_KEY = "lyric_font"
DESKTOP_LYRIC_KEY = "desktop_lyric"
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


THEME_MODE_VALUES = ("light", "dark", "system")


async def load_theme_mode(prefs) -> str:
    """读取主题模式，非法值回退为跟随系统。"""
    raw = await prefs.get(THEME_MODE_KEY)
    return raw if raw in THEME_MODE_VALUES else "system"


async def save_theme_mode(prefs, mode: str) -> None:
    if mode in THEME_MODE_VALUES:
        await prefs.set(THEME_MODE_KEY, mode)


async def load_lyric_offsets(prefs) -> dict[str, float]:
    """读取每首歌的歌词微调偏移（秒），键为曲目绝对路径。"""
    raw = await prefs.get(LYRIC_OFFSETS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except (TypeError, ValueError):
        return {}
    offsets: dict[str, float] = {}
    for key, value in data.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            offsets[str(key)] = float(value)
    return offsets


async def save_lyric_offset(prefs, key: str, offset: float) -> None:
    """保存某首歌的歌词微调偏移；偏移为 0 时移除记录。"""
    offsets = await load_lyric_offsets(prefs)
    if offset == 0:
        offsets.pop(key, None)
    else:
        offsets[key] = round(float(offset), 3)
    await prefs.set(LYRIC_OFFSETS_KEY, json.dumps(offsets, ensure_ascii=False))


async def load_lyric_font(prefs) -> float:
    """读取歌词字号（全局设置），非法值回退为默认字号。"""
    raw = await prefs.get(LYRIC_FONT_KEY)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return LYRIC_FONT_DEFAULT
    if not (LYRIC_FONT_MIN <= value <= LYRIC_FONT_MAX):
        return LYRIC_FONT_DEFAULT
    return value


async def save_lyric_font(prefs, size: float) -> None:
    """保存歌词字号（全局设置）。"""
    await prefs.set(LYRIC_FONT_KEY, float(size))


async def load_desktop_lyric(prefs) -> dict:
    """读取桌面歌词设置。

    返回 ``{"enabled": bool, "locked": bool, "font_size": float,
    "x": float | None, "y": float | None}``；缺失或损坏的字段按默认值补齐。
    """
    raw = None
    try:
        raw = await prefs.get(DESKTOP_LYRIC_KEY)
    except Exception:
        raw = None
    data: dict = {}
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except (TypeError, ValueError):
            data = {}

    def _number(key: str) -> float | None:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    font = _number("font_size")
    if font is None or not (
        DESKTOP_LYRIC_FONT_MIN <= font <= DESKTOP_LYRIC_FONT_MAX
    ):
        font = DESKTOP_LYRIC_FONT_DEFAULT

    return {
        "enabled": bool(data.get("enabled", False)),
        "locked": bool(data.get("locked", False)),
        "font_size": font,
        "x": _number("x"),
        "y": _number("y"),
    }


async def save_desktop_lyric(prefs, settings: dict) -> None:
    """保存桌面歌词设置（整体覆盖）。"""
    payload = {
        "enabled": bool(settings.get("enabled", False)),
        "locked": bool(settings.get("locked", False)),
        "font_size": float(
            settings.get("font_size", DESKTOP_LYRIC_FONT_DEFAULT)
        ),
        "x": settings.get("x"),
        "y": settings.get("y"),
    }
    await prefs.set(DESKTOP_LYRIC_KEY, json.dumps(payload, ensure_ascii=False))
