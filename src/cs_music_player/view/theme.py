"""主题：把「配色 + 明暗」交给 cs-ui 的主题运行时。

分工只有一句话：**本模块只决定「用哪个品牌色、哪一档明暗」，配色本身由
cs-ui 算**。

- 品牌色种子来自 :data:`cs_music_player.models.THEME_SEEDS`（10 套配色各一个 hex）；
- 明暗 / 跟随系统来自视觉模型里的 :class:`~cs_music_player.models.ThemeMode`；
- 46 个 M3 角色（表面、前景、容器、描边……）由 ``ui.core.palette`` 从种子解算，
  明暗两套一次给全（``page.theme`` + ``page.dark_theme``）。

相比早先自研一套调色板，这样做换来三件事：

1. **只有一处色值**：加一个配色 = 在种子表里加一行，不会再出现「浅色好看、
   深色忘了改」；
2. **切主题不掉帧**：界面里引用的都是角色名，Flutter 直接解析；换主题只是把
   两棵现成的主题树换上去，Python 不需要把所有控件重画一遍；
3. **对比度是算出来的**：主色按 WCAG 解明度（白字压上去 ≥4.5:1），深色模式的
   前景是解出来的深墨而不是固定的白 —— 手挑色值做不到这一点。

**不要**在这里写 ``Theme(...)``：那是 cs-ui 的活。本模块只调用
:func:`ui.apply_theme`，并在配色切换时把新种子写进全局主题状态。
"""

from __future__ import annotations

from collections.abc import Callable

from ui import IconData, Icons, Page, apply_theme, theme_state

from ..models import (
    ColorTheme,
    PlayMode,
    ThemeMode,
    name_of,
    seed_of,
)

__all__ = [
    "COLOR_ROLE_HINT",
    "PLAY_MODE_ICONS",
    "THEME_ICONS",
    "THEME_LABELS",
    "apply_color_theme",
    "sync_theme",
    "theme_label",
]

#: 播放模式 → 图标（顺序与 :class:`~cs_music_player.models.PlayMode` 一致）。
PLAY_MODE_ICONS: dict[PlayMode, IconData] = {
    PlayMode.SEQUENCE: Icons.REPEAT,
    PlayMode.LOOP_ONE: Icons.REPEAT_ONE,
    PlayMode.SHUFFLE: Icons.SHUFFLE,
}

#: 明暗模式 → 图标 / 文案（配色面板里的三段胶囊）。
THEME_ICONS: dict[ThemeMode, IconData] = {
    ThemeMode.LIGHT: Icons.LIGHT_MODE,
    ThemeMode.DARK: Icons.DARK_MODE,
    ThemeMode.SYSTEM: Icons.BRIGHTNESS_AUTO,
}
THEME_LABELS: dict[ThemeMode, str] = {
    ThemeMode.LIGHT: "浅色",
    ThemeMode.DARK: "深色",
    ThemeMode.SYSTEM: "跟随",
}

#: 配色样本卡上的一行小字：说明「点一下会发生什么」。
COLOR_ROLE_HINT = "点击即生效 · 明暗独立切换"


def theme_label(theme: ColorTheme) -> str:
    """配色的显示名。"""
    return name_of(theme)


def apply_color_theme(page: Page, color: ColorTheme) -> None:
    """只换品牌色（明暗不动）。

    换主色是**整页范围**的决定，所以写进 cs-ui 的全局主题状态；随后的
    :func:`sync_theme` 会把它落成 ``page.theme`` / ``page.dark_theme``。
    """
    theme_state().set_primary(seed_of(color))


def sync_theme(
    page: Page,
    color: ColorTheme,
    mode: ThemeMode | str,
    *,
    on_brightness: Callable[[str], None] | None = None,
) -> None:
    """把「配色 + 明暗」一次性落到页面上（幂等，可在每次渲染后调用）。

    Args:
        page: 页面。
        color: 配色主题。
        mode: 明暗模式；``system`` 交给 Flutter 跟随系统亮度。
        on_brightness: 系统亮度变化时的旁路回调（视觉模型据此更新自己的状态）。

    ``apply_theme`` 是**幂等**的：主题状态没变时它仍然重写两个 ``Theme``
    对象，所以调用方应按「配色 / 明暗」变化去调用（见 ``view/app.py`` 的
    ``use_effect`` 依赖表），不要每帧都调。
    """
    state = theme_state()
    # 字体族不在这里设：交给 cs-ui 按平台选系统字体（font_family 保持 None）。
    state.set_primary(seed_of(color))
    state.set_mode(str(mode))
    apply_theme(page, state, on_brightness=on_brightness)
