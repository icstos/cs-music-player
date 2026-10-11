"""程序组装根（composition root）：唯一「认识所有层」的地方。

设计意图：五个分层各自只依赖抽象，谁都不负责 `new` 具体实现——把这件事
集中在这里，分层内部的依赖方向才能保持单向。本模块不属于任何一层，
也不被任何一层导入。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import flet as ft

from .infra.audio import FletAudioEngine
from .infra.desktop_lyric import DesktopLyricWindow
from .infra.dispatch import FletLoopDispatcher
from .infra.lyrics_provider import LrclibLyricsProvider
from .infra.lyrics_repository import LocalLyricsRepository
from .infra.metadata import MutagenMetadataReader
from .infra.picker import install_directory_picker
from .infra.preferences import install_preferences
from .service.desktop_lyric import DesktopLyricService
from .service.folders import FolderHistoryService
from .service.library import LibraryService
from .service.lyrics import LyricsService
from .service.playback import PlaybackObserver, PlaybackService
from .models import DesktopLyricConfig
from .service.settings import SettingsService
from .view.app import PlayerApp
from .viewmodel import AppViewModel

__all__ = ["build_view_model", "run_app"]

#: 启动时的默认音量 / 倍速。
DEFAULT_VOLUME = 0.7
DEFAULT_SPEED = 1.0



def build_view_model(page: ft.Page) -> AppViewModel:
    """按「基础设施 → 服务 → 视图模型」的顺序装配整个应用。"""
    # —— 基础设施 —— #
    preferences = install_preferences(page)
    picker = install_directory_picker(page)
    metadata = MutagenMetadataReader()
    lyrics_repository = LocalLyricsRepository()
    lyrics_provider = LrclibLyricsProvider(metadata)
    dispatcher = FletLoopDispatcher(page)

    # —— 服务 —— #
    settings = SettingsService(preferences)
    library = LibraryService(metadata, lyrics_repository, preferences, picker)
    folders = FolderHistoryService(preferences)
    lyrics = LyricsService(lyrics_repository, lyrics_provider, preferences)

    def make_controller(
        on_command: Callable[[str], None],
        on_config_change: Callable[[DesktopLyricConfig], None],
    ) -> DesktopLyricWindow:
        """悬浮窗跑在自己的线程上，回调一律投递回 UI 事件循环。"""
        return DesktopLyricWindow(
            on_command=lambda name: dispatcher(lambda: on_command(name)),
            on_config_change=lambda config: dispatcher(
                lambda: on_config_change(config)
            ),
        )

    desktop_lyric = DesktopLyricService(make_controller, settings)

    def make_playback(observer: PlaybackObserver) -> PlaybackService:
        """引擎反过来需要观察者，用工厂消解构造顺序上的循环。"""
        return PlaybackService(
            lambda engine_observer: FletAudioEngine(
                page,
                engine_observer,
                volume=DEFAULT_VOLUME,
                speed=DEFAULT_SPEED,
            ),
            observer,
            volume=DEFAULT_VOLUME,
            speed=DEFAULT_SPEED,
        )

    async def close_window() -> None:
        try:
            await page.window.close()
        except Exception:
            pass

    return AppViewModel(
        playback_factory=make_playback,
        library=library,
        folders=folders,
        lyrics=lyrics,
        settings=settings,
        desktop_lyric=desktop_lyric,
        on_close_requested=lambda: page.run_task(close_window),
    )


async def run_app(page: ft.Page, startup_path: Path | None = None) -> None:
    """渲染主界面并把启动路径交给视图模型。"""
    view_model = build_view_model(page)
    page.on_disconnect = lambda e=None: view_model.shutdown()
    page.render(PlayerApp, page, view_model)
    page.run_task(view_model.initialize, startup_path)
