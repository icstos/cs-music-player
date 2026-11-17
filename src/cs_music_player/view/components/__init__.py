"""视图层组件：可复用的纯 props 驱动 UI 构件。"""

from __future__ import annotations

from .dialogs import build_sleep_dialog
from .format import (
    _fmt,
    _fmt_bitrate,
    _fmt_frequency,
    _fmt_size,
    _fmt_speed,
    _kv,
    fmt_duration,
)
from .lyric_settings import LyricSettingsEntry
from .lyrics import (
    LyricsLine,
    LyricsPanel,
    _lyric_active_font_size,
    _lyric_active_pad,
    _lyric_active_row_height,
    _lyric_row_height,
    _lyric_window,
    _lyric_window_rows,
)
from .player_bar import (
    PlayerBar,
    PlayControls,
    ProgressBar,
    SpeedControl,
    VolumeControl,
    _clamp_progress_value,
)
from .playlist import PlaylistItem, Sidebar
from .stage import MainStage
from .theme_picker import ThemeMenuButton, build_theme_menu
from .toolbar import DesktopLyricButton, SleepTimerButton

__all__ = [
    "DesktopLyricButton",
    "LyricSettingsEntry",
    "LyricsLine",
    "LyricsPanel",
    "MainStage",
    "PlayControls",
    "PlayerBar",
    "PlaylistItem",
    "ProgressBar",
    "Sidebar",
    "SleepTimerButton",
    "SpeedControl",
    "ThemeMenuButton",
    "build_theme_menu",
    "VolumeControl",
    "build_sleep_dialog",
    "fmt_duration",
    "_clamp_progress_value",
    "_fmt",
    "_fmt_bitrate",
    "_fmt_frequency",
    "_fmt_size",
    "_fmt_speed",
    "_kv",
    "_lyric_active_font_size",
    "_lyric_active_pad",
    "_lyric_active_row_height",
    "_lyric_row_height",
    "_lyric_window",
    "_lyric_window_rows",
]
