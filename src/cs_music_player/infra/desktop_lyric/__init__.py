"""桌面歌词基础设施层。

- :mod:`cs_music_player.infra.desktop_lyric.render`：纯 Pillow 的帧渲染，不碰 Win32。
- :mod:`cs_music_player.infra.desktop_lyric.window`：Win32 分层窗口与
  :class:`DesktopLyricWindow` 控制器。

:class:`DesktopLyricWindow` 结构上满足
:class:`cs_music_player.infra.ports.DesktopLyricPort`。
"""

from __future__ import annotations

from ...models import DesktopLyricConfig
from .render import (
    FONT_SIZE_DEFAULT,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    FONT_SIZE_STEP,
    Frame,
    load_font,
    render_frame,
    resolve_font_path,
    set_font_path,
    to_premultiplied_bgra,
    toolbar_width,
)
from .window import DesktopLyricWindow

__all__ = [
    "DesktopLyricConfig",
    "DesktopLyricWindow",
    "FONT_SIZE_DEFAULT",
    "FONT_SIZE_MAX",
    "FONT_SIZE_MIN",
    "FONT_SIZE_STEP",
    "Frame",
    "load_font",
    "render_frame",
    "resolve_font_path",
    "set_font_path",
    "to_premultiplied_bgra",
    "toolbar_width",
]
