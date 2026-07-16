"""本地歌词：扫描 lyrics 目录、匹配曲目、解析 LRC。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .constants import SUPPORTED_LYRICS_FORMATS

_LRC_TAG = re.compile(r"\[(\d+):(\d+)(?:\.(\d+))?[^\]]*\](.*)")


@dataclass(frozen=True)
class LyricLine:
    time: float
    text: str


def build_lyrics_index(lyrics_dir: Path) -> dict[str, Path]:
    """将 lyrics 目录下的歌词文件按文件名（小写 stem）建立索引。"""
    if not lyrics_dir.is_dir():
        return {}
    index: dict[str, Path] = {}
    for path in lyrics_dir.iterdir():
        if path.is_file() and path.suffix.lower() in SUPPORTED_LYRICS_FORMATS:
            index[path.stem.lower()] = path
    return index


def match_lyrics_path(
    lyrics_index: dict[str, Path], track_stem: str
) -> Path | None:
    """按曲目文件名（不含扩展名）匹配歌词文件。"""
    return lyrics_index.get(track_stem.lower())


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


def load_lyrics(path: Path) -> list[LyricLine]:
    """读取并解析歌词文件，失败时返回空列表。"""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="gbk")
        except Exception:
            return []
    except Exception:
        return []

    if path.suffix.lower() == ".lrc":
        parsed = parse_lrc(text)
        if parsed:
            return parsed
    return parse_plain_lyrics(text)


def current_line_index(lines: list[LyricLine], position: float) -> int:
    """根据当前播放位置返回应高亮的歌词行索引。"""
    if not lines:
        return -1
    if all(line.time == 0.0 for line in lines):
        return 0
    idx = -1
    for i, line in enumerate(lines):
        if line.time <= position:
            idx = i
        else:
            break
    return idx
