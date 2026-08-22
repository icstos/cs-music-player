"""UI 组件：纯函数 + props 驱动，由 @ft.component 自动管理重渲染。"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from .audio_player import Track
from .constants import MODE_ICONS, SPEED_PRESETS, palette
from .lyrics import LyricLine, current_line_index


def _fmt(seconds: float) -> str:
    """秒数 → ``m:ss`` 格式。"""
    if seconds <= 0 or seconds != seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def fmt_duration(seconds: float) -> str:
    """秒数 → 倒计时可读格式（``mm:ss`` / ``h:mm:ss``）。"""
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _fmt(seconds: float) -> str:
    """秒数 → ``m:ss`` 格式。"""
    if seconds <= 0 or seconds != seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _fmt_size(size: int) -> str:
    """字节数 → 可读文件大小。"""
    if size <= 0:
        return ""
    if size >= 1 << 30:
        return f"{size / (1 << 30):.2f} GB"
    if size >= 1 << 20:
        return f"{size / (1 << 20):.1f} MB"
    return f"{size / (1 << 10):.0f} KB"


def _fmt_frequency(hz: int) -> str:
    """采样率 Hz → ``44.1 kHz``。"""
    if hz <= 0:
        return ""
    return f"{hz / 1000:g} kHz"


def _fmt_bitrate(bps: int) -> str:
    """码率 bps → ``320 kbps``。"""
    if bps <= 0:
        return ""
    return f"{bps / 1000:g} kbps"


def _kv(label: str, value: str) -> str:
    """生成两列对齐的键值行：标签宽度不足 4 个全角字符时补全角空格。"""
    return f"{label}{'　' * (4 - len(label))}{value}"


def _track_info_tooltip(track: Track) -> ft.Tooltip:
    """曲目信息悬浮卡：延迟出现、跟随光标、深色质感卡片。"""
    header = [
        f"♪　{track.title or track.path.name}",
        _kv("歌手", track.artist or "未知"),
    ]
    rows: list[str] = []
    if track.duration > 0:
        rows.append(_kv("时长", _fmt(track.duration)))
    if track.album:
        rows.append(_kv("专辑", track.album))
    size = _fmt_size(track.file_size)
    if size:
        rows.append(_kv("大小", size))
    freq = _fmt_frequency(track.sample_rate)
    if freq:
        rows.append(_kv("采样率", freq))
    bitrate = _fmt_bitrate(track.bitrate)
    if bitrate:
        rows.append(_kv("码率", bitrate))
    if track.channels:
        rows.append(_kv("声道", str(track.channels)))
    if track.audio_format:
        rows.append(_kv("格式", track.audio_format))

    body = "\n".join(header + (["─" * 15, *rows] if rows else []))
    return ft.Tooltip(
        message=body,
        text_style=ft.TextStyle(
            size=11.5,
            height=1.65,
            color=ft.Colors.WHITE,
            letter_spacing=0.2,
        ),
        text_align=ft.TextAlign.START,
        padding=ft.Padding.symmetric(horizontal=14, vertical=11),
        decoration=ft.BoxDecoration(
            bgcolor=ft.Colors.with_opacity(0.97, palette.PRIMARY_DARK),
            border_radius=ft.BorderRadius.all(10),
            border=ft.Border.all(
                1, ft.Colors.with_opacity(0.28, ft.Colors.WHITE)
            ),
            shadows=[
                ft.BoxShadow(
                    blur_radius=22,
                    color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                    offset=ft.Offset(0, 6),
                )
            ],
        ),
        size_constraints=ft.BoxConstraints(max_width=340),
        prefer_below=True,
        vertical_offset=10,
        wait_duration=ft.Duration(milliseconds=600),
        exit_duration=ft.Duration(milliseconds=120),
    )


def _clamp_progress_value(value: float, duration: float) -> float:
    """将播放进度限制在 Slider 合法范围内，避免浮点误差导致越界。"""
    if duration <= 0:
        return 0.0
    ratio = value / duration
    if ratio != ratio:
        return 0.0
    return max(0.0, min(1.0, ratio))


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


# ── 播放列表 ── #


@ft.component
def PlaylistItem(
    index: int,
    track: Track,
    is_selected: bool,
    is_playing: bool,
    on_select: Callable[[Track], None],
    on_play: Callable[[Track], None],
    on_favorite: Callable[[Track], None],
) -> ft.Control:
    def _on_select(e: ft.ControlEvent) -> None:
        on_select(track)

    async def _on_play(e: ft.ControlEvent) -> None:
        await on_play(track)

    async def _on_favorite(e: ft.ControlEvent) -> None:
        await on_favorite(track)

    row = ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    f"{index + 1:02d}",
                    size=12,
                    color=palette.PRIMARY_LIGHT if is_selected else palette.TEXT_MUTED,
                    width=28,
                    text_align=ft.TextAlign.CENTER,
                ),
                _track_cover(
                    track, size=40, is_current=is_selected, is_playing=is_playing
                ),
                ft.Column(
                    [
                        ft.Text(
                            track.title,
                            size=13,
                            weight=ft.FontWeight.W_600
                            if is_selected
                            else ft.FontWeight.W_500,
                            color=palette.TEXT_MAIN if is_selected else palette.TEXT_DIM,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    track.artist or track.path.parent.name,
                                    size=11,
                                    color=palette.TEXT_MUTED,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                ft.Text(
                                    _fmt(track.duration),
                                    size=11,
                                    color=palette.TEXT_MUTED,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.FAVORITE
                    if track.favorite
                    else ft.Icons.FAVORITE_BORDER,
                    icon_color=palette.PRIMARY_LIGHT if track.favorite else palette.TEXT_MUTED,
                    icon_size=18,
                    tooltip="取消收藏" if track.favorite else "收藏",
                    on_click=_on_favorite,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.all(4),
                        overlay_color=ft.Colors.with_opacity(0.06, palette.PRIMARY),
                    ),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=palette.PRIMARY_BG if is_selected else ft.Colors.TRANSPARENT,
        border=ft.Border(
            left=ft.BorderSide(3, palette.PRIMARY if is_selected else ft.Colors.TRANSPARENT),
        ),
        padding=ft.Padding.only(left=8, right=8, top=6, bottom=6),
        ink=True,
    )

    return ft.GestureDetector(
        on_tap=_on_select,
        on_double_tap=_on_play,
        tooltip=_track_info_tooltip(track),
        content=row,
    )


@ft.component
def Sidebar(
    tracks: list[Track],
    selected: int,
    playing_track: Track | None,
    search: str,
    show_favorites: bool,
    total_count: int,
    on_search: Callable[[str], None],
    on_toggle_favorites: Callable[[bool], None],
    on_select: Callable[[Track], None],
    on_play: Callable[[Track], None],
    on_favorite: Callable[[Track], None],
    is_playing: bool,
    on_search_focus: Callable[[], None],
    on_search_blur: Callable[[], None],
) -> ft.Control:
    selected_track = tracks[selected] if 0 <= selected < len(tracks) else None

    header = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "音乐库",
                            size=16,
                            weight=ft.FontWeight.W_700,
                            color=palette.TEXT_MAIN,
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            f"{len(tracks)} / {total_count} 首",
                            size=11,
                            color=palette.TEXT_MUTED,
                        ),
                    ],
                ),
                ft.TextField(
                    value=search,
                    on_change=lambda e: on_search(str(e.control.value or "")),
                    on_focus=lambda e: on_search_focus(),
                    on_blur=lambda e: on_search_blur(),
                    hint_text="搜索歌曲或文件夹",
                    prefix_icon=ft.Icons.SEARCH,
                    border_radius=12,
                    dense=True,
                    content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_color=palette.BORDER,
                    focused_border_color=palette.PRIMARY_LIGHT,
                    bgcolor=palette.SURFACE,
                ),
                ft.Row(
                    [
                        ft.Chip(
                            label=ft.Text("全部", size=12),
                            selected=not show_favorites,
                            on_select=lambda e: on_toggle_favorites(False),
                        ),
                        ft.Chip(
                            label=ft.Text("收藏", size=12),
                            leading=ft.Icon(ft.Icons.FAVORITE, size=16),
                            selected=show_favorites,
                            on_select=lambda e: on_toggle_favorites(True),
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
        ),
        padding=ft.Padding.only(left=16, right=16, top=16, bottom=12),
        border=ft.Border(bottom=ft.BorderSide(1, palette.BORDER)),
    )

    if not tracks:
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.LIBRARY_MUSIC_OUTLINED, size=48, color=palette.TEXT_MUTED),
                    ft.Text(
                        "暂无歌曲", size=14, weight=ft.FontWeight.W_600, color=palette.TEXT_DIM
                    ),
                    ft.Text(
                        "点击右上角导入音乐文件夹",
                        size=12,
                        color=palette.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        body = ft.ListView(
            controls=[
                PlaylistItem(
                    i,
                    t,
                    t is selected_track,
                    is_playing and t is playing_track,
                    on_select,
                    on_play,
                    on_favorite,
                )
                for i, t in enumerate(tracks)
            ],
            spacing=2,
            padding=ft.Padding.symmetric(vertical=8),
            expand=True,
        )

    return ft.Container(
        content=ft.Column([header, body], spacing=0, expand=True),
        width=340,
        bgcolor=palette.SURFACE,
        border=ft.Border(right=ft.BorderSide(1, palette.BORDER)),
        expand=False,
    )


# ── 进度条 ── #


@ft.component
def ProgressBar(
    position: float,
    duration: float,
    dragging: ft.MutableRef[bool],
    on_seek: Callable[[float], None],
    *,
    compact: bool = False,
) -> ft.Control:
    local_value, set_local = ft.use_state(0.0)

    def on_change(e: ft.ControlEvent) -> None:
        set_local(float(e.control.value))
        dragging.current = True

    async def on_change_end(e: ft.ControlEvent) -> None:
        if duration > 0:
            await on_seek(float(e.control.value) * duration)
        dragging.current = False

    value = (
        local_value if dragging.current else _clamp_progress_value(position, duration)
    )

    slider = ft.Slider(
        min=0,
        max=1,
        value=value,
        active_color=palette.PRIMARY,
        inactive_color=palette.BORDER,
        thumb_color=palette.PRIMARY_LIGHT,
        on_change=on_change,
        on_change_end=on_change_end,
        expand=True,
    )

    if compact:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(_fmt(position), size=10, color=palette.TEXT_MUTED, width=34),
                    slider,
                    ft.Text(
                        _fmt(duration),
                        size=10,
                        color=palette.TEXT_MUTED,
                        width=34,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.03, palette.PRIMARY),
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )

    return ft.Column(
        [
            slider,
            ft.Row(
                [
                    ft.Text(_fmt(position), size=11, color=palette.TEXT_MUTED),
                    ft.Container(expand=True),
                    ft.Text(_fmt(duration), size=11, color=palette.TEXT_MUTED),
                ]
            ),
        ],
        spacing=2,
    )


# ── 音量控制 ── #


@ft.component
def VolumeControl(
    volume: float, on_change: Callable[[float], None], *, compact: bool = False
) -> ft.Control:
    icon = (
        ft.Icons.VOLUME_MUTE
        if volume == 0
        else ft.Icons.VOLUME_DOWN
        if volume < 0.5
        else ft.Icons.VOLUME_UP
    )
    slider_width = 100 if compact else 120
    return ft.Row(
        [
            ft.IconButton(
                icon=icon,
                icon_color=palette.TEXT_DIM,
                icon_size=20,
                tooltip="音量",
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            ft.Slider(
                min=0,
                max=1,
                value=volume,
                active_color=palette.PRIMARY,
                inactive_color=palette.BORDER,
                thumb_color=palette.PRIMARY_LIGHT,
                on_change=lambda e: on_change(float(e.control.value)),
                width=slider_width,
            ),
        ],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


# ── 播放控制按钮组 ── #


@ft.component
def PlayControls(
    is_playing: bool,
    mode: str,
    has_tracks: bool,
    on_toggle: Callable,
    on_prev: Callable,
    on_next: Callable,
    on_mode: Callable,
    *,
    compact: bool = False,
) -> ft.Control:
    play_size = 44 if compact else 52
    skip_size = 28 if compact else 32
    play_icon_size = 26 if compact else 30
    play_icon = ft.Icons.PAUSE_ROUNDED if is_playing else ft.Icons.PLAY_ARROW_ROUNDED
    play_icon_control: ft.Control = ft.Icon(
        play_icon, color=palette.SURFACE, size=play_icon_size
    )
    if not is_playing:
        play_icon_control = ft.Container(
            content=play_icon_control,
            margin=ft.Margin.only(left=2),
        )
    return ft.Row(
        [
            ft.Container(
                content=ft.IconButton(
                    icon=MODE_ICONS[mode],
                    icon_color=palette.PRIMARY if has_tracks else palette.TEXT_MUTED,
                    icon_size=20,
                    tooltip=mode,
                    on_click=on_mode,
                    disabled=not has_tracks,
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                ),
                bgcolor=ft.Colors.with_opacity(0.04, palette.PRIMARY),
                border_radius=10,
                padding=ft.Padding.all(2),
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_PREVIOUS_ROUNDED,
                icon_color=palette.TEXT_MAIN if has_tracks else palette.TEXT_MUTED,
                icon_size=skip_size,
                tooltip="上一曲",
                on_click=on_prev,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
            ft.Container(
                content=play_icon_control,
                width=play_size,
                height=play_size,
                alignment=ft.Alignment.CENTER,
                bgcolor=palette.PRIMARY if has_tracks else palette.TEXT_MUTED,
                border_radius=play_size // 2,
                on_click=on_toggle if has_tracks else None,
                ink=True,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=12,
                    color=ft.Colors.with_opacity(0.2, palette.PRIMARY),
                    offset=ft.Offset(0, 4),
                )
                if has_tracks
                else None,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_NEXT_ROUNDED,
                icon_color=palette.TEXT_MAIN if has_tracks else palette.TEXT_MUTED,
                icon_size=skip_size,
                tooltip="下一曲",
                on_click=on_next,
                disabled=not has_tracks,
                style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=4 if compact else 8,
    )


# ── 播放速度 ── #


def _fmt_speed(rate: float) -> str:
    """倍速 → 可读标签，如 ``1.0x``、``1.25x``。"""
    return f"{rate:g}x"


@ft.component
def SpeedControl(
    speed: float,
    on_change: Callable[[float], None],
) -> ft.Control:
    """倍速选择：紧凑按钮显示当前速度，点击弹出预设菜单。"""
    is_default = speed == 1.0

    items: list[ft.PopupMenuItem] = []
    for preset in SPEED_PRESETS:
        selected = abs(speed - preset) < 1e-9
        items.append(
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.CHECK
                            if selected
                            else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=15,
                            color=palette.PRIMARY if selected else palette.TEXT_MUTED,
                        ),
                        ft.Text(
                            _fmt_speed(preset),
                            size=12,
                            weight=ft.FontWeight.W_600
                            if selected
                            else ft.FontWeight.NORMAL,
                            color=palette.TEXT_MAIN if selected else palette.TEXT_DIM,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda e, r=preset: on_change(r),
            )
        )

    return ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Text(
                _fmt_speed(speed),
                size=11,
                weight=ft.FontWeight.W_600,
                color=palette.PRIMARY if not is_default else palette.TEXT_DIM,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=(
                palette.PRIMARY_TINT_12 if not is_default else ft.Colors.TRANSPARENT
            ),
        ),
        items=items,
        tooltip="播放速度",
        menu_position=ft.PopupMenuPosition.UNDER,
        style=ft.ButtonStyle(padding=ft.Padding.all(2)),
    )


# ── 底部播放栏 ── #


@ft.component
def PlayerBar(
    track: Track | None,
    is_playing: bool,
    position: float,
    duration: float,
    volume: float,
    speed: float,
    mode: str,
    dragging: ft.MutableRef[bool],
    on_toggle: Callable,
    on_prev: Callable,
    on_next: Callable,
    on_mode: Callable,
    on_seek: Callable[[float], None],
    on_volume: Callable[[float], None],
    on_speed: Callable[[float], None],
) -> ft.Control:
    title = "未选择歌曲" if track is None else track.title
    subtitle = "导入音乐文件夹开始播放" if track is None else track.path.parent.name

    return ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        _track_cover(
                            track,
                            size=46,
                            is_playing=is_playing,
                            letter_fallback=True,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    title,
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=palette.TEXT_MAIN,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    subtitle,
                                    size=10,
                                    color=palette.TEXT_MUTED,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=10,
                    width=260,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=ProgressBar(
                        position, duration, dragging, on_seek, compact=True
                    ),
                    expand=True,
                    margin=ft.Margin.only(left=8, right=8),
                ),
                ft.Row(
                    [
                        PlayControls(
                            is_playing,
                            mode,
                            track is not None,
                            on_toggle,
                            on_prev,
                            on_next,
                            on_mode,
                            compact=True,
                        ),
                        ft.Container(width=6),
                        SpeedControl(speed, on_speed),
                        ft.Container(width=4),
                        VolumeControl(volume, on_volume, compact=True),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=palette.SURFACE,
        border=ft.Border(top=ft.BorderSide(1, palette.BORDER)),
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color=ft.Colors.with_opacity(0.04, palette.TEXT_MAIN),
            offset=ft.Offset(0, -4),
        ),
    )


# ── 歌词面板 ── #


@ft.component
def LyricsLine(
    text: str,
    is_current: bool,
) -> ft.Control:
    return ft.Container(
        content=ft.Text(
            text,
            size=18 if is_current else 15,
            weight=ft.FontWeight.W_700 if is_current else ft.FontWeight.NORMAL,
            color=palette.PRIMARY if is_current else palette.TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(vertical=6 if is_current else 4),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


@ft.component
def LyricsPanel(
    lines: list[LyricLine],
    position: float,
    has_lyrics_file: bool,
    offset: float = 0.0,
) -> ft.Control:
    active = current_line_index(lines, position, offset)

    if not has_lyrics_file:
        body = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=36, color=palette.TEXT_MUTED),
                    ft.Text("暂无歌词", size=13, color=palette.TEXT_DIM),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    elif not lines:
        body = ft.Container(
            content=ft.Text("歌词文件无法解析", size=13, color=palette.TEXT_DIM),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        body = ft.Container(
            content=ft.ListView(
                controls=[
                    LyricsLine(line.text, i == active)
                    for i, line in enumerate(lines)
                ],
                spacing=2,
                padding=ft.Padding.symmetric(horizontal=28, vertical=8),
                expand=True,
            ),
            expand=True,
        )

    return body


# ── 睡眠定时器 ── #

_SLEEP_PRESETS_MINUTES = (10, 15, 30, 45, 60)


@ft.component
def SleepTimerButton(
    remaining: float,
    on_click: Callable[[], None],
) -> ft.Control:
    """睡眠定时器入口：仅图标，激活时强调色提示。"""
    active = remaining > 0
    tooltip = (
        f"睡眠定时器（剩余 {fmt_duration(remaining)}）"
        if active
        else "睡眠定时器"
    )
    return ft.IconButton(
        icon=ft.Icons.BEDTIME if active else ft.Icons.BEDTIME_OUTLINED,
        icon_color=palette.ACCENT if active else palette.TEXT_DIM,
        icon_size=20,
        tooltip=tooltip,
        on_click=lambda e: on_click(),
        style=ft.ButtonStyle(
            padding=ft.Padding.all(8),
            overlay_color=ft.Colors.with_opacity(0.08, palette.PRIMARY),
        ),
    )


def build_sleep_dialog(
    remaining: float,
    on_start: Callable[[int], None],
    on_cancel: Callable[[], None],
    on_close: Callable[[], None],
) -> ft.AlertDialog:
    """睡眠定时器配置弹窗：快捷预设 + 时/分/秒自定义，激活时可查看剩余并取消。"""
    hours_ref = ft.Ref()
    minutes_ref = ft.Ref()
    seconds_ref = ft.Ref()

    def _field(ref: ft.Ref, label: str) -> ft.TextField:
        return ft.TextField(
            ref=ref,
            label=label,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=66,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            border_radius=8,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=8),
        )

    def start_custom(e: ft.ControlEvent) -> None:
        def _val(ref: ft.Ref) -> int:
            try:
                return int((ref.current.value or "").strip() or 0)
            except (TypeError, ValueError):
                return 0

        total = _val(hours_ref) * 3600 + _val(minutes_ref) * 60 + _val(seconds_ref)
        if total > 0:
            on_start(total)

    presets = ft.Row(
        [
            ft.Chip(
                label=ft.Text(f"{m} 分钟", size=12),
                on_select=lambda e, m=m: on_start(m * 60),
            )
            for m in _SLEEP_PRESETS_MINUTES
        ],
        spacing=6,
        wrap=True,
    )

    custom = ft.Row(
        [
            _field(hours_ref, "时"),
            _field(minutes_ref, "分"),
            _field(seconds_ref, "秒"),
            ft.FilledButton(
                content=ft.Text("开始", size=12),
                on_click=start_custom,
                style=ft.ButtonStyle(
                    bgcolor=palette.PRIMARY,
                    color=ft.Colors.WHITE,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                ),
            ),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    body: list[ft.Control] = [
        ft.Text("倒计时结束后自动关闭软件", size=12, color=palette.TEXT_DIM),
        ft.Container(height=4),
        presets,
        ft.Divider(height=1, color=palette.BORDER),
        custom,
    ]
    if remaining > 0:
        body.extend(
            [
                ft.Divider(height=1, color=palette.BORDER),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TIMER, size=16, color=palette.ACCENT),
                        ft.Text(
                            f"剩余 {fmt_duration(remaining)}",
                            size=13,
                            weight=ft.FontWeight.W_600,
                            color=palette.ACCENT,
                        ),
                        ft.Container(expand=True),
                        ft.TextButton(
                            content=ft.Text("取消定时", size=12, color=palette.TEXT_DIM),
                            on_click=lambda e: on_cancel(),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ]
        )

    return ft.AlertDialog(
        modal=True,
        title=ft.Text("睡眠定时器", size=16, weight=ft.FontWeight.W_700),
        content=ft.Container(
            content=ft.Column(body, spacing=10, width=320),
            padding=ft.Padding.only(top=4),
        ),
        actions=[
            ft.TextButton(
                content=ft.Text("关闭", size=12, color=palette.TEXT_DIM),
                on_click=lambda e: on_close(),
            )
        ],
    )


# ── 歌词同步（隐藏式微调） ── #


def _offset_label(offset: float) -> str:
    """偏移秒数 → 可读文案（正值=提前，负值=延后）。"""
    if offset == 0:
        return "同步"
    direction = "提前" if offset > 0 else "延后"
    return f"{direction} {abs(round(offset, 3)):g}s"


@ft.component
def LyricSyncControl(
    offset: float,
    track_path: str,
    on_adjust: Callable[[float], None],
) -> ft.Control:
    """歌词同步控件：默认仅显示右上角小图标，点击展开微调面板。

    已微调时图标旁显示状态胶囊（如“提前 0.3s”），切歌自动收起。
    """
    expanded, set_expanded = ft.use_state(False)
    # 切歌时自动收起，避免残留面板干扰新歌
    ft.use_effect(lambda: set_expanded(False), [track_path])

    adjusted = offset != 0

    def step_button(text: str, delta: float, tooltip: str) -> ft.Control:
        return ft.Container(
            content=ft.Text(
                text,
                size=11,
                weight=ft.FontWeight.W_600,
                color=palette.PRIMARY,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=palette.PRIMARY_TINT_12,
            ink=True,
            tooltip=tooltip,
            on_click=lambda e, d=delta: on_adjust(d),
        )

    def reset_button() -> ft.Control:
        return ft.Container(
            content=ft.Icon(ft.Icons.REFRESH, size=15, color=palette.TEXT_DIM),
            padding=ft.Padding.all(5),
            border_radius=8,
            ink=True,
            tooltip="恢复歌词同步",
            on_click=lambda e: (on_adjust(-offset), set_expanded(False)),
        )

    toggle = ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.TUNE,
                    size=16,
                    color=palette.ACCENT if adjusted else palette.TEXT_MUTED,
                ),
                ft.Text(
                    _offset_label(offset),
                    size=11,
                    weight=ft.FontWeight.W_600 if adjusted else ft.FontWeight.NORMAL,
                    color=palette.ACCENT if adjusted else palette.TEXT_MUTED,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=14,
        bgcolor=palette.ACCENT_TINT_10 if adjusted else ft.Colors.TRANSPARENT,
        ink=True,
        tooltip="歌词同步调整",
        on_click=lambda e: set_expanded(not expanded),
    )

    bar = ft.Container(
        content=ft.Row(
            [
                step_button("提前 0.1s", 0.1, "歌词提前 100ms"),
                step_button("延后 0.1s", -0.1, "歌词延后 100ms"),
                step_button("提前 1s", 1.0, "歌词提前 1000ms"),
                step_button("延后 1s", -1.0, "歌词延后 1000ms"),
                *([reset_button()] if adjusted else []),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=palette.SURFACE_SOFT,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
    )

    return ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [ft.Container(expand=True), toggle],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.only(left=28, right=28, top=2, bottom=4),
            ),
            ft.AnimatedSwitcher(
                content=bar if expanded else ft.Container(),
                transition=ft.AnimatedSwitcherTransition.FADE,
                duration=200,
                switch_in_curve=ft.AnimationCurve.EASE_OUT,
                switch_out_curve=ft.AnimationCurve.EASE_IN,
            ),
        ],
        spacing=0,
    )


# ── 主舞台（封面 + 歌词） ── #


@ft.component
def MainStage(
    track: Track | None,
    is_playing: bool,
    lyrics: list[LyricLine],
    position: float,
    has_lyrics_file: bool,
    lyric_offset: float = 0.0,
    on_adjust_lyric: Callable[[float], None] | None = None,
) -> ft.Control:
    title = "未选择歌曲" if track is None else track.title
    subtitle = "请导入音乐文件夹" if track is None else track.path.parent.name
    cover_size = 220

    cover = ft.Container(
        content=_track_cover(
            track,
            size=cover_size,
            is_playing=is_playing,
            letter_fallback=True,
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=32,
            color=ft.Colors.with_opacity(0.15, palette.TEXT_MAIN),
            offset=ft.Offset(0, 12),
        ),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
    )

    if track and is_playing:
        cover = ft.Container(
            content=ft.Stack(
                [
                    cover,
                    ft.Container(
                        content=ft.Icon(ft.Icons.GRAPHIC_EQ, color=palette.ACCENT, size=20),
                        alignment=ft.Alignment(1, -1),
                        margin=ft.Margin.only(top=8, right=8),
                        bgcolor=palette.ACCENT_TINT_10,
                        border_radius=20,
                        padding=ft.Padding.all(6),
                    ),
                ],
            ),
        )

    track_path = str(track.path) if track is not None else ""
    lyrics_section = ft.Column(
        [
            (
                LyricSyncControl(lyric_offset, track_path, on_adjust_lyric)
                if has_lyrics_file and on_adjust_lyric is not None
                else ft.Container()
            ),
            ft.Container(
                content=LyricsPanel(
                    lyrics, position, has_lyrics_file, offset=lyric_offset
                ),
                expand=True,
            ),
        ],
        spacing=0,
        expand=True,
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            cover,
                            ft.Container(height=8),
                            ft.Text(
                                title,
                                size=22,
                                weight=ft.FontWeight.W_700,
                                color=palette.TEXT_MAIN,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                subtitle,
                                size=13,
                                color=palette.TEXT_DIM,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=ft.Padding.only(top=32, left=32, right=32, bottom=16),
                ),
                lyrics_section,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        ),
        expand=True,
        bgcolor=palette.BG,
    )
