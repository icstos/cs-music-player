"""视图层：基于 cs-ui（``ui``）的声明式渲染与事件分发。

本层**不包含任何业务逻辑**，只做两件事：把视图模型的状态渲染成控件、
把用户操作转发给视图模型。因此这里只允许依赖 :mod:`cs_music_player.viewmodel`
与 :mod:`cs_music_player.models`，UI 侧只认 ``ui`` 一个包——既不 import flet、
代码里也不出现 flet 前缀（唯一的缺口登记在
:mod:`~cs_music_player.view.components.primitives`），分层测试会盯住这一条。

- :mod:`~cs_music_player.view.tokens` —— 语义角色（哪个位置用哪个 M3 角色）
- :mod:`~cs_music_player.view.theme` —— 配色 → 品牌色种子、明暗与图标映射
- :mod:`~cs_music_player.view.components` —— 可复用的纯 props 构件
"""

from __future__ import annotations

from .app import PlayerApp, build_history_menu
from .theme import (
    PLAY_MODE_ICONS,
    THEME_ICONS,
    THEME_LABELS,
    apply_color_theme,
    sync_theme,
    theme_label,
)

__all__ = [
    "PLAY_MODE_ICONS",
    "THEME_ICONS",
    "THEME_LABELS",
    "PlayerApp",
    "apply_color_theme",
    "build_history_menu",
    "sync_theme",
    "theme_label",
]
