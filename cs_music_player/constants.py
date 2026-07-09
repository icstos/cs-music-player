"""共享常量：文件格式、播放模式、配色、图标映射。"""

from __future__ import annotations

import flet as ft

# ── 文件格式 ── #
SUPPORTED_FORMATS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")

# ── 播放模式 ── #
MODE_SEQUENCE = "顺序播放"
MODE_LOOP_ONE = "单曲循环"
MODE_SHUFFLE = "随机播放"
MODE_ORDER = (MODE_SEQUENCE, MODE_LOOP_ONE, MODE_SHUFFLE)
MODE_ICONS = {
    MODE_SEQUENCE: ft.Icons.REPEAT,
    MODE_LOOP_ONE: ft.Icons.REPEAT_ONE,
    MODE_SHUFFLE: ft.Icons.SHUFFLE,
}

# ── 配色 ── #
BRAND = ft.Colors.DEEP_PURPLE
BRAND_400 = ft.Colors.DEEP_PURPLE_400
SURFACE = "#1e1b2e"
SURFACE_SOFT = "#27233a"
TEXT_MAIN = ft.Colors.WHITE
TEXT_DIM = ft.Colors.GREY_400
BG_COLOR = "#13111c"
