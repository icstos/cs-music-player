"""本地歌词的索引、匹配与解析（LRC / 纯文本）。

对外只暴露 :class:`LocalLyricsRepository`，它实现
:class:`cs_music_player.infra.ports.LyricsRepositoryPort`。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from ..models import LYRIC_EXTENSIONS, LyricLine

__all__ = [
    "LocalLyricsRepository",
    "build_lyrics_index",
    "load_lyrics",
    "match_lyrics_path",
    "parse_lrc",
    "parse_plain_lyrics",
]

_LRC_TAG = re.compile(r"\[(\d+):(\d+)(?:\.(\d+))?[^\]]*\](.*)")


def build_lyrics_index(lyrics_dir: Path) -> dict[str, Path]:
    """将 lyrics 目录下的歌词文件按文件名（小写 stem）建立索引。"""
    if not lyrics_dir.is_dir():
        return {}
    index: dict[str, Path] = {}
    for path in lyrics_dir.iterdir():
        if path.is_file() and path.suffix.lower() in LYRIC_EXTENSIONS:
            index[path.stem.lower()] = path
    return index


def match_lyrics_path(index: Mapping[str, Path], track_stem: str) -> Path | None:
    """按曲目文件名（不含扩展名）匹配歌词文件。"""
    return index.get(track_stem.lower())


def _timestamp_to_seconds(minutes: str, seconds: str, fractional: str | None) -> float:
    frac = 0.0
    if fractional:
        # LRC 小数部分可能是 2 位（百分秒）或 3 位（毫秒）
        digits = fractional.ljust(3, "0")[:3]
        frac = int(digits) / 1000.0
    return int(minutes) * 60 + int(seconds) + frac


def parse_lrc(content: str) -> list[LyricLine]:
    """解析 LRC 格式歌词，返回按时间排序的行列表。"""
    lines: list[LyricLine] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _LRC_TAG.match(line)
        if not match:
            continue
        minutes, seconds, fractional, text = match.groups()
        text = text.strip()
        if not text:
            continue
        t = _timestamp_to_seconds(minutes, seconds, fractional)
        lines.append(LyricLine(time=t, text=text))
    lines.sort(key=lambda item: item.time)
    return lines


def parse_plain_lyrics(content: str) -> list[LyricLine]:
    """纯文本歌词：每行一条，无时间轴。"""
    return [
        LyricLine(time=0.0, text=line.strip())
        for line in content.splitlines()
        if line.strip()
    ]


def _read_text(path: Path) -> str | None:
    """按 UTF-8 读取，失败回退 GBK；再失败返回 ``None``。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="gbk")
        except Exception:
            return None
    except Exception:
        return None


def load_lyrics(path: Path) -> list[LyricLine]:
    """读取并解析歌词文件，失败时返回空列表。"""
    text = _read_text(path)
    if text is None:
        return []
    if path.suffix.lower() == ".lrc":
        parsed = parse_lrc(text)
        if parsed:
            return parsed
    return parse_plain_lyrics(text)


class LocalLyricsRepository:
    """基于本地文件系统的 :class:`LyricsRepositoryPort` 实现。"""

    def index(self, lyrics_dir: Path) -> dict[str, Path]:
        """把歌词目录下的文件按「小写文件名」建索引。"""
        return build_lyrics_index(lyrics_dir)

    def match(self, index: Mapping[str, Path], stem: str) -> Path | None:
        """按曲目文件名匹配歌词文件。"""
        return match_lyrics_path(index, stem)

    def read(self, path: Path) -> list[LyricLine]:
        """读取并解析歌词文件；失败时返回空列表。"""
        return load_lyrics(path)
