"""模型层：核心数据结构、状态枚举、常量。

本层是所有层都可以依赖的最底层：**只放数据与常量，不含任何业务逻辑**，
也不导入 ``flet`` / ``mutagen`` / ``Pillow`` 等第三方库，因此可以在任何
环境下被导入与单测。
"""

from __future__ import annotations

from .constants import (
    AUDIO_EXTENSIONS,
    DESKTOP_LYRIC_FONT_DEFAULT,
    DESKTOP_LYRIC_FONT_MAX,
    DESKTOP_LYRIC_FONT_MIN,
    DESKTOP_LYRIC_FONT_STEP,
    DARK_PALETTE,
    FONT_FAMILY,
    FONT_FAMILY_FILE,
    LIGHT_PALETTE,
    LYRIC_ACTIVE_DELTA,
    LYRIC_EXTENSIONS,
    LYRIC_FONT_DEFAULT,
    LYRIC_FONT_MAX,
    LYRIC_FONT_MIN,
    LYRIC_LINE_FACTOR,
    LYRIC_OFFSET_STEP_COARSE,
    LYRIC_OFFSET_STEP_FINE,
    LYRIC_ROW_GAP_RATIO,
    MAX_RECENT_FOLDERS,
    SPEED_MAX,
    SPEED_MIN,
    SLEEP_PRESET_MINUTES,
    SPEED_PRESETS,
    SUPPORTED_FORMATS,
    SUPPORTED_LYRICS_FORMATS,
)
from .lyrics import LyricLine
from .playback import (
    MODE_LOOP_ONE,
    MODE_ORDER,
    MODE_SEQUENCE,
    MODE_SHUFFLE,
    PlayMode,
)
from .settings import (
    THEME_MODES,
    DesktopLyricConfig,
    ThemeMode,
    clamp_desktop_lyric_font,
    clamp_lyric_font,
)
from .track import AudioMetadata, StartupLoad, TagText, Track, track_key

__all__ = [
    "AUDIO_EXTENSIONS",
    "DARK_PALETTE",
    "DESKTOP_LYRIC_FONT_DEFAULT",
    "DESKTOP_LYRIC_FONT_MAX",
    "DESKTOP_LYRIC_FONT_MIN",
    "DESKTOP_LYRIC_FONT_STEP",
    "AudioMetadata",
    "DesktopLyricConfig",
    "FONT_FAMILY",
    "FONT_FAMILY_FILE",
    "LIGHT_PALETTE",
    "LYRIC_ACTIVE_DELTA",
    "LYRIC_EXTENSIONS",
    "LYRIC_FONT_DEFAULT",
    "LYRIC_FONT_MAX",
    "LYRIC_FONT_MIN",
    "LYRIC_LINE_FACTOR",
    "LYRIC_OFFSET_STEP_COARSE",
    "LYRIC_OFFSET_STEP_FINE",
    "LYRIC_ROW_GAP_RATIO",
    "LyricLine",
    "MAX_RECENT_FOLDERS",
    "MODE_LOOP_ONE",
    "MODE_ORDER",
    "MODE_SEQUENCE",
    "MODE_SHUFFLE",
    "PlayMode",
    "SPEED_MAX",
    "SPEED_MIN",
    "SLEEP_PRESET_MINUTES",
    "SPEED_PRESETS",
    "SUPPORTED_FORMATS",
    "SUPPORTED_LYRICS_FORMATS",
    "StartupLoad",
    "TagText",
    "THEME_MODES",
    "ThemeMode",
    "clamp_desktop_lyric_font",
    "clamp_lyric_font",
    "Track",
    "track_key",
]
