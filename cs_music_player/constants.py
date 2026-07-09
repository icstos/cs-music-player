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

# ── 配色系统（专业蓝 · 科技风）── #
# 主色阶
PRIMARY = "#2563eb"        # Blue 600 — 主交互色
PRIMARY_LIGHT = "#60a5fa"  # Blue 400 — 悬停 / 高亮
PRIMARY_DARK = "#1e40af"   # Blue 800 — 按下态

# 背景层
BG = "#0a0e1a"             # 最深底色
SURFACE = "#121826"        # 卡片背景
SURFACE_SOFT = "#1a2333"   # 浅卡片 / 次级面板
PRIMARY_BG = "#1c2d52"     # 主色浅底（选中态 / 焦点底）

# 描边
BORDER = "#243044"         # 默认描边
BORDER_FOCUS = "#3b5fbd"   # 焦点描边

# 文字层级
TEXT_MAIN = "#e8ecf1"      # 主文字
TEXT_DIM = "#7a8ba3"       # 次级文字
TEXT_MUTED = "#4a5b73"     # 辅助文字

# 透明度主色（用于图标背景等）
PRIMARY_TINT_15 = ft.Colors.with_opacity(0.15, PRIMARY)
PRIMARY_TINT_20 = ft.Colors.with_opacity(0.20, PRIMARY)
