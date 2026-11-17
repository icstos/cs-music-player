"""视图模型所需的抽象接口（依赖倒置：高层定义自己需要的契约）。

需求里的「高层依赖抽象接口，不依赖具体实现」在这里落地：``AppViewModel``
只认这些 ``Protocol``，``service`` 层的具体类靠**结构化子类型**满足它们——
服务层不需要 import 本模块，依赖方向因此仍然是单向的
（view → viewmodel → service → infra）。

这些接口只列出视图模型真正用到的那部分能力，比整份服务 API 窄得多。
``tests/test_architecture.py`` 会逐一校验具体服务确实满足对应的契约。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models import (
    ColorTheme,
    DesktopLyricConfig,
    LyricLine,
    PlayMode,
    StartupLoad,
    ThemeMode,
    Track,
)

__all__ = [
    "DesktopLyricOps",
    "FolderHistoryOps",
    "LibraryOps",
    "LyricsOps",
    "PlaybackOps",
    "SettingsOps",
]


@runtime_checkable
class PlaybackOps(Protocol):
    """播放服务对视图模型暴露的能力。"""

    def set_tracks(self, tracks: list[Track]) -> None:
        """整体替换播放列表。"""
        ...

    async def play_at(self, index: int) -> None:
        """播放指定索引的曲目。"""
        ...

    async def toggle(self) -> None:
        """播放 / 暂停切换。"""
        ...

    async def next(self, auto: bool = False) -> None:
        """下一首。"""
        ...

    async def prev(self) -> None:
        """上一首。"""
        ...

    async def seek(self, seconds: float) -> None:
        """跳转到指定秒数。"""
        ...

    def set_volume(self, value: float) -> None:
        """设置音量。"""
        ...

    def set_speed(self, value: float) -> None:
        """设置播放倍速。"""
        ...

    def cycle_mode(self) -> PlayMode:
        """循环切换播放模式。"""
        ...

    def shutdown(self) -> None:
        """释放引擎资源。"""
        ...


@runtime_checkable
class LibraryOps(Protocol):
    """音乐库服务对视图模型暴露的能力。"""

    async def choose_music_folder(self, title: str = ...) -> Path | None:
        """弹出目录选择框。"""
        ...

    async def favorites(self) -> set[str]:
        """读取收藏集合。"""
        ...

    def load_directory(self, directory: Path) -> list[Track]:
        """扫描目录下的音频文件。"""
        ...

    def resolve_startup(self, path: Path) -> StartupLoad | None:
        """解析启动路径。"""
        ...

    async def save_favorites(self, favorites: set[str]) -> None:
        """保存收藏集合。"""
        ...


@runtime_checkable
class FolderHistoryOps(Protocol):
    """文件夹历史服务对视图模型暴露的能力。"""

    async def recent_folders(self) -> list[str]:
        """读取最近打开的文件夹。"""
        ...

    async def remember_folder(self, folder: str) -> list[str]:
        """把文件夹记入历史。"""
        ...

    async def clear_recent_folders(self) -> None:
        """清空最近打开记录。"""
        ...

    async def pinned_folders(self) -> set[str]:
        """读取固定文件夹集合。"""
        ...

    async def toggle_pinned(self, folder: str) -> set[str]:
        """切换文件夹的固定状态。"""
        ...


@runtime_checkable
class LyricsOps(Protocol):
    """歌词服务对视图模型暴露的能力。"""

    def load(self, path: Path | None) -> list[LyricLine]:
        """读取并解析歌词文件。"""
        ...

    async def fetch_missing(self, track: Track) -> list[LyricLine] | None:
        """后台补齐缺失歌词。"""
        ...

    async def offset_for(self, track: Track | None) -> float:
        """读取某首歌的歌词偏移。"""
        ...

    async def set_offset(self, track: Track, offset: float) -> None:
        """保存某首歌的歌词偏移。"""
        ...


@runtime_checkable
class SettingsOps(Protocol):
    """设置服务对视图模型暴露的能力。"""

    async def theme_mode(self) -> ThemeMode:
        """读取主题模式。"""
        ...

    async def save_theme_mode(self, mode: ThemeMode) -> None:
        """保存主题模式。"""
        ...

    async def color_theme(self) -> ColorTheme:
        """读取配色主题。"""
        ...

    async def save_color_theme(self, theme: ColorTheme) -> None:
        """保存配色主题。"""
        ...

    async def lyric_font(self) -> float:
        """读取歌词字号。"""
        ...

    async def save_lyric_font(self, size: float) -> None:
        """保存歌词字号。"""
        ...


@runtime_checkable
class DesktopLyricOps(Protocol):
    """桌面歌词服务对视图模型暴露的能力。"""

    async def restore(self) -> DesktopLyricConfig:
        """把持久化配置灌回悬浮窗。"""
        ...

    def subscribe(self, listener: object) -> Callable[[], None]:
        """订阅悬浮窗事件。"""
        ...

    def set_visible(self, visible: bool) -> None:
        """显示 / 隐藏悬浮窗。"""
        ...

    def toggle_visible(self) -> bool:
        """切换显隐。"""
        ...

    def toggle_locked(self) -> bool:
        """切换锁定状态。"""
        ...

    def nudge_font(self, delta: float) -> None:
        """增减字号。"""
        ...

    def reset_font(self) -> None:
        """恢复默认字号。"""
        ...

    def stop(self) -> None:
        """关闭悬浮窗。"""
        ...
