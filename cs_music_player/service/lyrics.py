"""歌词服务：读取本地歌词、按曲目持久化时间偏移、后台补齐缺失歌词。

只依赖抽象接口（``LyricsRepositoryPort`` / ``LyricsProviderPort`` /
``PreferencesPort``），不感知 LRC 文件长什么样、也不感知 HTTP。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..infra.ports import (
    LYRIC_OFFSETS_KEY,
    LyricsProviderPort,
    LyricsRepositoryPort,
    PreferencesPort,
)
from ..models import LyricLine, Track, track_key

__all__ = ["LyricsService", "current_line_index"]


def current_line_index(
    lines: list[LyricLine], position: float, offset: float = 0.0
) -> int:
    """根据当前播放位置返回应高亮的歌词行索引。

    ``offset`` 为歌词微调偏移（秒）：正值使歌词提前显示，负值延后。
    无歌词返回 ``-1``；纯文本歌词（全部时间为 0）恒高亮第 0 行。
    """
    if not lines:
        return -1
    position += offset
    if all(line.time == 0.0 for line in lines):
        return 0
    idx = -1
    for i, line in enumerate(lines):
        if line.time <= position:
            idx = i
        else:
            break
    return idx


async def _decode_offsets(prefs: PreferencesPort) -> dict[str, float]:
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


class LyricsService:
    """歌词相关的业务流程。

    Args:
        repository: 本地歌词的索引 / 匹配 / 解析。
        provider: 在线歌词来源（缺失歌词时后台补齐）。
        preferences: 持久化歌词偏移。
        on_updated: 后台补齐成功后的通知钩子（可选），参数为补齐的曲目。
    """

    def __init__(
        self,
        repository: LyricsRepositoryPort,
        provider: LyricsProviderPort,
        preferences: PreferencesPort,
        *,
        on_updated: Callable[[Track], None] | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._prefs = preferences
        self._on_updated = on_updated
        self._in_flight: set[str] = set()

    # —— 本地歌词 —— #

    def load(self, path: Path | None) -> list[LyricLine]:
        """读取并解析歌词文件；路径为空时返回空列表。"""
        if path is None:
            return []
        return self._repository.read(path)

    # —— 时间偏移（按曲目持久化）—— #

    async def offset_for(self, track: Track | None) -> float:
        """读取某首歌的歌词偏移；没有记录返回 ``0.0``。"""
        if track is None:
            return 0.0
        offsets = await _decode_offsets(self._prefs)
        return offsets.get(track_key(track.path), 0.0)

    async def set_offset(self, track: Track, offset: float) -> None:
        """保存某首歌的歌词偏移；偏移为 0 时移除记录。"""
        offsets = await _decode_offsets(self._prefs)
        key = track_key(track.path)
        if offset == 0:
            offsets.pop(key, None)
        else:
            offsets[key] = round(float(offset), 3)
        await self._prefs.set(
            LYRIC_OFFSETS_KEY, json.dumps(offsets, ensure_ascii=False)
        )

    # —— 后台补齐 —— #

    async def fetch_missing(self, track: Track) -> list[LyricLine] | None:
        """曲目缺歌词时从在线来源补齐并落盘。

        Returns:
            新解析出的歌词行；无需下载 / 下载失败时返回 ``None``。
        """
        if track.lyrics_path is not None:
            return None
        key = track_key(track.path)
        if key in self._in_flight:
            return None
        self._in_flight.add(key)
        try:
            path = await self._provider.download(track)
            if path is None:
                return None
            track.lyrics_path = path
            lines = self._repository.read(path)
            if self._on_updated is not None:
                self._on_updated(track)
            return lines
        finally:
            self._in_flight.discard(key)
