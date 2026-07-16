"""共享常量：文件格式、播放模式、配色系统、图标映射。"""

from __future__ import annotations

import flet as ft

# ── 文件格式 ── #
SUPPORTED_FORMATS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
SUPPORTED_LYRICS_FORMATS = (".lrc", ".txt")

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

# ── 配色系统（清爽、克制、偏音乐 App 风格）── #
PRIMARY = "#2563eb"
PRIMARY_LIGHT = "#3b82f6"
PRIMARY_DARK = "#1d4ed8"
ACCENT = "#7c3aed"
ACCENT_LIGHT = "#8b5cf6"

BG = "#f5f7fb"
SURFACE = "#ffffff"
SURFACE_SOFT = "#eef2f7"
PRIMARY_BG = "#eff6ff"

BORDER = "#dbe3ee"
BORDER_FOCUS = "#93c5fd"

TEXT_MAIN = "#0f172a"
TEXT_DIM = "#475569"
TEXT_MUTED = "#94a3b8"

PRIMARY_TINT_08 = ft.Colors.with_opacity(0.08, PRIMARY)
PRIMARY_TINT_12 = ft.Colors.with_opacity(0.12, PRIMARY)
PRIMARY_TINT_16 = ft.Colors.with_opacity(0.16, PRIMARY)
ACCENT_TINT_10 = ft.Colors.with_opacity(0.10, ACCENT)
