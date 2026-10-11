"""服务/业务层：编排核心业务流程。

只依赖 :mod:`cs_music_player.infra.ports` 里的抽象接口与
:mod:`cs_music_player.models` 里的数据结构，不感知任何具体技术实现
（本包内不出现 ``flet`` / ``mutagen`` / ``Pillow``）。

名字采用 PEP 562 惰性转出：``from cs_music_player.service import PlaybackService``
照旧可用，但 ``import cs_music_player.service`` 本身不会拉起任何子模块。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 仅供类型检查器与 IDE 解析，运行期不执行
    from .desktop_lyric import DesktopLyricFactory, DesktopLyricListener, DesktopLyricService
    from .folders import (
        FolderHistoryService,
        normalize_folder_path,
        push_recent_folder,
        toggle_pinned_folder,
    )
    from .library import LibraryService
    from .lyrics import LyricsService, current_line_index
    from .playback import (
        EngineFactory,
        PlaybackCallbacks,
        PlaybackObserver,
        PlaybackService,
        next_index,
        prev_index,
    )
    from .settings import SettingsService, clamp_lyric_font
    from .sleep import SleepTimerService, run_sleep_countdown

__all__ = [
    "DesktopLyricFactory",
    "DesktopLyricListener",
    "DesktopLyricService",
    "EngineFactory",
    "FolderHistoryService",
    "LibraryService",
    "LyricsService",
    "PlaybackCallbacks",
    "PlaybackObserver",
    "PlaybackService",
    "SettingsService",
    "SleepTimerService",
    "clamp_lyric_font",
    "current_line_index",
    "normalize_folder_path",
    "push_recent_folder",
    "toggle_pinned_folder",
    "next_index",
    "prev_index",
    "run_sleep_countdown",
]

#: 名字 -> 定义它的子模块（相对于本包）。
_LAZY_EXPORTS = {
    "DesktopLyricFactory": "desktop_lyric",
    "DesktopLyricListener": "desktop_lyric",
    "DesktopLyricService": "desktop_lyric",
    "EngineFactory": "playback",
    "FolderHistoryService": "folders",
    "LibraryService": "library",
    "LyricsService": "lyrics",
    "PlaybackCallbacks": "playback",
    "PlaybackObserver": "playback",
    "PlaybackService": "playback",
    "SettingsService": "settings",
    "SleepTimerService": "sleep",
    "clamp_lyric_font": "settings",
    "current_line_index": "lyrics",
    "normalize_folder_path": "folders",
    "push_recent_folder": "folders",
    "toggle_pinned_folder": "folders",
    "next_index": "playback",
    "prev_index": "playback",
    "run_sleep_countdown": "sleep",
}


def __getattr__(name: str) -> Any:
    """首次访问时才导入对应子模块，并把结果缓存进本模块命名空间。"""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
