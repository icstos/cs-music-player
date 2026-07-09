"""顶层应用组件：集中持有 UI 状态，组装布局，桥接播放器与视图。"""

from __future__ import annotations

from pathlib import Path

import flet as ft

from .audio_player import Player, PlayerCallbacks, Track, load_tracks_from_directory
from .constants import PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, TEXT_MAIN, MODE_SEQUENCE
from .ui import NowPlaying, PlayControls, Playlist, ProgressBar, VolumeControl, card


@ft.component
def PlayerApp(page: ft.Page) -> ft.Control:
    # —— UI 状态 —— #
    tracks, set_tracks = ft.use_state(list[Track]())
    current, set_current = ft.use_state(-1)
    is_playing, set_is_playing = ft.use_state(False)
    position, set_position = ft.use_state(0.0)
    duration, set_duration = ft.use_state(0.0)
    volume, set_volume = ft.use_state(0.7)
    mode, set_mode = ft.use_state(MODE_SEQUENCE)

    dragging = ft.use_ref(False)
    player_ref = ft.use_ref(None)
    picker_ref = ft.use_ref(None)

    # —— 初始化播放器 + FilePicker —— #
    def setup() -> None:
        player_ref.current = Player(
            PlayerCallbacks(
                on_position=set_position,
                on_duration=set_duration,
                on_play_state=set_is_playing,
                on_track_change=set_current,
            ),
            page,
        )
        picker = ft.FilePicker()
        page.services.append(picker)
        page.update()
        picker_ref.current = picker

    ft.use_effect(setup, dependencies=[])

    # —— 事件处理 —— #

    async def on_import(e: ft.ControlEvent) -> None:
        picker = picker_ref.current
        if picker is None:
            return
        directory = await picker.get_directory_path("选择音乐文件夹")
        if not directory:
            return
        files = load_tracks_from_directory(Path(directory))
        if not files:
            return
        player = player_ref.current
        if player:
            player.set_tracks(files)
        set_tracks(files)
        set_current(0)
        set_position(0.0)
        set_duration(files[0].duration)

    async def on_toggle(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.toggle()

    async def on_next(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.next()

    async def on_prev(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.prev()

    def on_volume(value: float) -> None:
        set_volume(value)
        if player_ref.current:
            player_ref.current.set_volume(value)

    def on_mode(e: ft.ControlEvent) -> None:
        if player_ref.current:
            set_mode(player_ref.current.cycle_mode())

    async def on_select(index: int) -> None:
        if player_ref.current:
            await player_ref.current.play_at(index)

    async def on_seek(seconds: float) -> None:
        if player_ref.current:
            await player_ref.current.seek(seconds)
            set_position(seconds)

    # —— 布局 —— #
    track = tracks[current] if 0 <= current < len(tracks) else None

    header = ft.Row(
        [
            ft.Icon(ft.Icons.LIBRARY_MUSIC, color=PRIMARY_LIGHT, size=28),
            ft.Text(
                "CS 音乐播放器", size=22, weight=ft.FontWeight.BOLD, color=TEXT_MAIN
            ),
            ft.Container(expand=True),
            ft.Button(
                content="打开文件夹",
                icon=ft.Icons.FOLDER_OPEN,
                on_click=on_import,
                style=ft.ButtonStyle(
                    bgcolor={
                        ft.ControlState.DEFAULT: PRIMARY,
                        ft.ControlState.HOVERED: PRIMARY_DARK,
                    },
                    color=ft.Colors.WHITE,
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    return ft.Column(
        [
            header,
            card([NowPlaying(track, is_playing)], soft=True),
            card(
                [
                    ProgressBar(position, duration, dragging, on_seek),
                    PlayControls(
                        is_playing,
                        mode,
                        bool(tracks),
                        on_toggle,
                        on_prev,
                        on_next,
                        on_mode,
                    ),
                    VolumeControl(volume, on_volume),
                ]
            ),
            Playlist(tracks, current, on_select),
        ],
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
