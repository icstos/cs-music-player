"""基础设施层对外暴露的抽象接口（依赖倒置的「接口」一侧）。

高层模块（service / viewmodel）只依赖这里的 :class:`typing.Protocol`，
具体实现在 :mod:`cs_music_player.infra` 的其他模块中，由程序的组装根
（``main.py`` 调用的 :func:`cs_music_player.view.app.create_app`）注入。

本模块不做任何导入期副作用：不导入 ``flet``、不连接网络、不建窗。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..models import (
    AudioMetadata,
    DesktopLyricConfig,
    LyricLine,
    TagText,
    Track,
)

__all__ = [
    "DESKTOP_LYRIC_KEY",
    "FAVORITES_KEY",
    "LYRIC_FONT_KEY",
    "LYRIC_OFFSETS_KEY",
    "PINNED_FOLDERS_KEY",
    "RECENT_FOLDERS_KEY",
    "THEME_MODE_KEY",
    "AudioEngineObserver",
    "AudioEnginePort",
    "DesktopLyricPort",
    "DirectoryPickerPort",
    "Dispatcher",
    "LyricsProviderPort",
    "LyricsRepositoryPort",
    "MetadataPort",
    "PreferencesPort",
]


# ── 持久化的键名（属于「抽象契约」：服务层只认这些名字，不认实现）── #

FAVORITES_KEY = "favorite_tracks"
RECENT_FOLDERS_KEY = "recent_folders"
PINNED_FOLDERS_KEY = "pinned_folders"
THEME_MODE_KEY = "theme_mode"
LYRIC_OFFSETS_KEY = "lyric_offsets"
LYRIC_FONT_KEY = "lyric_font"
DESKTOP_LYRIC_KEY = "desktop_lyric"


# ── 持久化 ── #


@runtime_checkable
class PreferencesPort(Protocol):
    """键值持久化（Flet ``SharedPreferences`` 的最小契约）。"""

    async def get(self, key: str) -> Any:
        """读取一个键；不存在返回 ``None``。"""
        ...

    async def set(self, key: str, value: Any) -> None:
        """写入一个键。"""
        ...


# ── 音频元数据 ── #


class MetadataPort(Protocol):
    """读取音频文件的时长 / 标签 / 内嵌封面。"""

    def read(self, path: Path) -> AudioMetadata:
        """读取元数据；失败时返回默认值而非抛错。"""
        ...

    def cover_data_uri(self, path: Path) -> str | None:
        """提取内嵌封面并编码为 data URI；没有封面时返回 ``None``。"""
        ...

    def read_tag_text(self, path: Path) -> TagText:
        """读取标签里的标题 / 歌手 / 专辑原文；读取失败时返回空值。"""
        ...


# ── 歌词 ── #


class LyricsRepositoryPort(Protocol):
    """本地歌词的索引、匹配与解析。"""

    def index(self, lyrics_dir: Path) -> dict[str, Path]:
        """把歌词目录下的文件按「小写文件名（不含扩展名）」建索引。"""
        ...

    def match(self, index: Mapping[str, Path], stem: str) -> Path | None:
        """按曲目文件名匹配歌词文件。"""
        ...

    def read(self, path: Path) -> list[LyricLine]:
        """读取并解析歌词文件；失败时返回空列表。"""
        ...


class LyricsProviderPort(Protocol):
    """在线歌词来源；成功时把歌词落盘并返回文件路径。"""

    async def download(self, track: Track) -> Path | None:
        """为曲目下载歌词；失败或未找到返回 ``None``。"""
        ...


# ── 音频播放 ── #


class AudioEngineObserver(Protocol):
    """播放引擎 → 上层的回调接口。"""

    def on_position(self, seconds: float) -> None:
        """播放进度（秒）。"""
        ...

    def on_duration(self, seconds: float) -> None:
        """曲目时长（秒）。"""
        ...

    def on_play_state(self, playing: bool) -> None:
        """播放 / 暂停状态变化。"""
        ...

    def on_completed(self) -> None:
        """当前曲目自然播放结束。"""
        ...


class AudioEnginePort(Protocol):
    """底层音频引擎（实现见 :class:`cs_music_player.infra.audio.FletAudioEngine`）。"""

    @property
    def playing(self) -> bool:
        """引擎当前是否处于播放状态。"""
        ...

    def set_volume(self, value: float) -> None:
        """设置音量（0~1）。"""
        ...

    def set_speed(self, value: float) -> None:
        """设置播放倍速。"""
        ...

    async def load(self, path: Path, *, autoplay: bool = True) -> None:
        """装载曲目；``autoplay`` 为真时立即开始播放。"""
        ...

    async def set_paused(self, paused: bool) -> None:
        """暂停 / 继续。"""
        ...

    async def seek(self, seconds: float) -> None:
        """跳转到指定秒数。"""
        ...

    def dispose(self) -> None:
        """释放底层资源。"""
        ...


# ── 文件选择 / 桌面歌词 / 线程调度 ── #


class DirectoryPickerPort(Protocol):
    """系统目录选择框。"""

    async def pick_directory(self, title: str) -> str | None:
        """弹出目录选择框；用户取消时返回 ``None``。"""
        ...


class DesktopLyricPort(Protocol):
    """桌面歌词悬浮窗控制器。"""

    @property
    def config(self) -> DesktopLyricConfig:
        """当前配置。"""
        ...

    def apply_config(self, config: DesktopLyricConfig) -> None:
        """整体应用一份配置（启动时灌入持久化设置）。"""
        ...

    def set_lyrics(self, lines: Sequence[str]) -> None:
        """更新歌词文本。"""
        ...

    def set_active(self, index: int) -> None:
        """更新当前高亮的行号。"""
        ...

    def set_playing(self, playing: bool) -> None:
        """更新播放状态（决定按钮画播放还是暂停）。"""
        ...

    def set_visible(self, visible: bool) -> None:
        """显示 / 隐藏悬浮窗。"""
        ...

    def set_locked(self, locked: bool, *, hint: bool = True) -> None:
        """锁定（鼠标穿透）/ 解锁。"""
        ...

    def set_font_size(self, size: float) -> None:
        """设置字号。"""
        ...

    def center(self) -> None:
        """回到默认停放位置。"""
        ...

    def stop(self) -> None:
        """关闭悬浮窗并结束窗口线程。"""
        ...


class Dispatcher(Protocol):
    """把一次回调投递回 UI 事件循环（跨线程安全）。"""

    def __call__(self, callback: Callable[[], None]) -> None:
        """在当前线程调用，把 ``callback`` 排到 UI 线程执行。"""
        ...
