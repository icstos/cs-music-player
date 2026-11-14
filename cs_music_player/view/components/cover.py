"""曲目封面：内嵌图 / 首字母 / 音符图标三种占位。"""

from __future__ import annotations

from ui import Container, Icons, Text, ft

from ...models import Track
from .. import tokens as t

__all__ = ["cover_radius", "track_cover"]


def cover_radius(size: int) -> int:
    """封面圆角按尺寸等比收放：小缩略图不能太圆，大封面不能太方。"""
    return max(8, size // 8)


def track_cover(
    track: Track | None,
    *,
    size: int,
    is_playing: bool = False,
    is_current: bool = False,
    letter_fallback: bool = False,
) -> ft.Control:
    """曲目封面。

    Args:
        track: 曲目；``None`` 表示「还没有歌」，画一个音符占位。
        size: 边长（逻辑像素）。
        is_playing: 正在播放——占位底色改用强调色，一眼能看出「响的是这首」。
        is_current: 当前选中——图标占位的底色和图标色跟着主色走。
        letter_fallback: 无内嵌图时用首字母而不是音符图标。
    """
    radius = cover_radius(size)
    letter = "♪" if track is None else (track.title[:1].upper() or "♪")
    letter_size = max(14, size // 2)

    if track is not None and track.cover_src:
        return Container(
            content=ft.Image(
                src=track.cover_src,
                width=size,
                height=size,
                fit=ft.BoxFit.COVER,
                gapless_playback=True,
                # 内嵌图解码失败时不能让那块地方空着：退回首字母
                error_content=Container(
                    content=Text(
                        letter,
                        size=letter_size,
                        weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_PRIMARY,
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
            ),
            width=size,
            height=size,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=radius,
        )

    if letter_fallback:
        return Container(
            content=Text(
                letter,
                size=letter_size,
                weight=ft.FontWeight.W_700,
                color=ft.Colors.ON_TERTIARY if is_playing else ft.Colors.ON_PRIMARY,
            ),
            width=size,
            height=size,
            alignment=ft.Alignment.CENTER,
            bgcolor=t.ACCENT if is_playing else ft.Colors.PRIMARY,
            border_radius=radius,
        )

    return Container(
        content=ft.Icon(
            Icons.GRAPHIC_EQ if is_current and is_playing else Icons.MUSIC_NOTE,
            color=ft.Colors.PRIMARY if is_current else t.TEXT_SOFT,
            size=max(16, size // 2),
        ),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor=t.SELECTED_BG if is_current else t.PANEL_HIGH,
        border_radius=radius,
    )
