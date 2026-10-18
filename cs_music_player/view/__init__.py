"""视图层：纯 Flet UI 的声明式渲染与事件分发。

本层**不包含任何业务逻辑**，只做两件事：把视图模型的状态渲染成控件、
把用户操作转发给视图模型。因此这里只允许依赖 :mod:`cs_music_player.viewmodel`
与 :mod:`cs_music_player.models`——绝不导入 ``service`` / ``infra``。
"""

from __future__ import annotations

from .app import PlayerApp
from .theme import (
    MODE_ICONS,
    THEME_ICONS,
    THEME_LABELS,
    Palette,
    apply_palette,
    build_dark_theme,
    build_light_theme,
    palette,
    sync_page_theme,
    theme_label,
)

__all__ = [
    "MODE_ICONS",
    "THEME_ICONS",
    "THEME_LABELS",
    "Palette",
    "PlayerApp",
    "apply_palette",
    "build_dark_theme",
    "build_light_theme",
    "palette",
    "sync_page_theme",
    "theme_label",
]
