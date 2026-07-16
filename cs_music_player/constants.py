"""共享常量：文件格式、播放模式、配色系统、图标映射。"""

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

# ── 配色系统（专业蓝 · 科技风 · 浅色主题）── #
# 主色阶
PRIMARY = "#2563eb"        # Blue 600 — 主交互色
PRIMARY_LIGHT = "#3b82f6"  # Blue 500 — 图标 / 高亮
PRIMARY_DARK = "#1d4ed8"   # Blue 700 — 按下态

# 背景层
BG = "#f8fafc"             # Slate 50 — 页面底色
SURFACE = "#ffffff"        # 白色卡片
SURFACE_SOFT = "#f1f5f9"   # Slate 100 — 浅卡片 / 次级面板
PRIMARY_BG = "#eff6ff"     # Blue 50 — 选中态浅蓝底

# 描边
BORDER = "#e2e8f0"         # Slate 200 — 默认描边
BORDER_FOCUS = "#93c5fd"   # Blue 300 — 焦点描边

# 文字层级
TEXT_MAIN = "#1e293b"      # Slate 800 — 主文字
TEXT_DIM = "#64748b"       # Slate 500 — 次级文字
TEXT_MUTED = "#94a3b8"     # Slate 400 — 辅助文字

# 透明度主色（用于图标背景等）
PRIMARY_TINT_08 = ft.Colors.with_opacity(0.08, PRIMARY)
PRIMARY_TINT_12 = ft.Colors.with_opacity(0.12, PRIMARY)
