"""曲目封面：内嵌图 / 音乐图标 / 首字母三种占位。"""

from __future__ import annotations

import flet as ft

from ...models import Track
from ..theme import palette

__all__ = ["_track_cover"]


def _track_cover(
    track: Track | None,
    *,
    size: int,
    is_playing: bool = False,
    is_current: bool = False,
    letter_fallback: bool = False,
) -> ft.Control:
    """曲目封面：有内嵌图则显示，否则图标或首字母占位。"""
    letter = "♪" if track is None else (track.title[:1].upper() or "♪")
    if track and track.cover_src:
        return ft.Container(
            content=ft.Image(
                src=track.cover_src,
                width=size,
                height=size,
                fit=ft.BoxFit.COVER,
                gapless_playback=True,
                error_content=ft.Container(
                    content=ft.Text(
                        letter,
                        size=max(14, size // 2),
                        weight=ft.FontWeight.W_700,
                        color=palette.SURFACE,
                    ),
                    alignment=ft.Alignment.CENTER,
                ),
            ),
            width=size,
            height=size,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border_radius=max(8, size // 8),
        )

    if letter_fallback:
        return ft.Container(
            content=ft.Text(
                letter,
                size=max(14, size // 2),
                weight=ft.FontWeight.W_700,
                color=palette.SURFACE,
            ),
            width=size,
            height=size,
            alignment=ft.Alignment.CENTER,
            bgcolor=palette.ACCENT if is_playing else palette.PRIMARY,
            border_radius=max(8, size // 8),
        )

    return ft.Container(
        content=ft.Icon(
            ft.Icons.GRAPHIC_EQ if is_current and is_playing else ft.Icons.MUSIC_NOTE,
            color=palette.PRIMARY if is_current else palette.TEXT_MUTED,
            size=max(16, size // 2),
        ),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor=palette.PRIMARY_TINT_12 if is_current else palette.SURFACE_SOFT,
        border_radius=max(8, size // 8),
    )
