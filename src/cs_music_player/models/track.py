"""曲目数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def track_key(path: Path) -> str:
    """曲目的唯一标识：绝对路径字符串（收藏 / 歌词偏移都以它为键）。"""
    return str(path.resolve())


@dataclass
class AudioMetadata:
    """从音频文件读出的元数据（读取失败时全部取默认值）。"""

    duration: float = 0.0
    artist: str = ""
    album: str = ""
    sample_rate: int = 0
    bitrate: int = 0
    channels: int = 0


@dataclass(frozen=True)
class TagText:
    """音频标签里的原始文本（多值标签只取第一个值）。

    与 :class:`Track` 上的字段刻意区分开：``Track.artist`` 是给界面看的
    （多值用 ``" / "`` 连接），而在线歌词检索要的是标签里的**原值**。
    """

    title: str = ""
    artist: str = ""
    album: str = ""


@dataclass
class Track:
    """一首曲目。``title`` / ``audio_format`` 未给定时由文件名推导。"""

    path: Path
    title: str = ""
    artist: str = ""
    duration: float = 0.0
    lyrics_path: Path | None = None
    favorite: bool = False
    cover_src: str | None = None
    album: str = ""
    file_size: int = 0
    sample_rate: int = 0
    bitrate: int = 0
    channels: int = 0
    audio_format: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.path.stem
        if not self.audio_format:
            self.audio_format = self.path.suffix[1:].upper() or "UNKNOWN"


@dataclass(frozen=True)
class StartupLoad:
    """启动时加载的曲目列表与播放目标。"""

    tracks: list[Track] = field(default_factory=list)
    play_index: int = 0
    autoplay: bool = False
