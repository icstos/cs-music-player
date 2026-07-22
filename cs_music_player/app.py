"""顶层应用组件：集中持有 UI 状态，组装布局，桥接播放器与视图。"""

from __future__ import annotations

from pathlib import Path

import flet as ft

from .audio_player import (
    Player,
    PlayerCallbacks,
    Track,
    load_tracks_from_directory,
    resolve_startup_load,
)
from .constants import (
    BG,
    PRIMARY,
    PRIMARY_DARK,
    SURFACE,
    TEXT_DIM,
    TEXT_MAIN,
    MODE_SEQUENCE,
)
from .lyrics import load_lyrics
from .store import apply_favorites, load_favorites, save_favorites, track_key
from .ui import MainStage, PlayerBar, Sidebar


@ft.component
def PlayerApp(page: ft.Page, startup_path: str | None = None) -> ft.Control:
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(
        color_scheme_seed=PRIMARY,
        use_material3=True,
        scaffold_bgcolor=BG,
        canvas_color=BG,
        card_bgcolor=SURFACE,
    )
    page.dark_theme = ft.Theme(
        color_scheme_seed="#8b5cf6",
        use_material3=True,
        scaffold_bgcolor="#0b1220",
        canvas_color="#0b1220",
        card_bgcolor="#111827",
    )
    tracks, set_tracks = ft.use_state(list[Track]())
    selected, set_selected = ft.use_state(-1)
    current, set_current = ft.use_state(-1)
    is_playing, set_is_playing = ft.use_state(False)
    position, set_position = ft.use_state(0.0)
    duration, set_duration = ft.use_state(0.0)
    volume, set_volume = ft.use_state(0.7)
    mode, set_mode = ft.use_state(MODE_SEQUENCE)
    lyrics, set_lyrics = ft.use_state(list())
    search, set_search = ft.use_state("")
    show_favorites, set_show_favorites = ft.use_state(False)

    dragging = ft.use_ref(False)
    player_ref = ft.use_ref(None)
    picker_ref = ft.use_ref(None)
    favorites_ref = ft.use_ref(set[str]())
    search_focused_ref = ft.use_ref(False)

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

    async def apply_tracks(
        files: list[Track],
        *,
        play_index: int = 0,
        autoplay: bool = False,
    ) -> None:
        favorites_ref.current = await load_favorites(page.shared_preferences)
        apply_favorites(files, favorites_ref.current)
        player = player_ref.current
        if player:
            player.set_tracks(files)
            if autoplay and 0 <= play_index < len(files):
                await player.play_at(play_index)
        set_tracks(files)
        set_selected(play_index if files else -1)
        if autoplay and 0 <= play_index < len(files):
            set_position(0.0)
            set_duration(files[play_index].duration)
            set_lyrics([])
            return
        set_current(-1)
        set_position(0.0)
        set_duration(files[play_index].duration if files else 0.0)
        set_lyrics([])
        set_is_playing(False)

    def init_startup() -> None:
        if not startup_path:
            return

        async def run() -> None:
            load = resolve_startup_load(Path(startup_path))
            if load is None:
                return
            await apply_tracks(
                load.tracks,
                play_index=load.play_index,
                autoplay=load.autoplay,
            )

        page.run_task(run)

    ft.use_effect(init_startup, dependencies=[])

    def refresh_lyrics() -> None:
        idx = current if current >= 0 else selected
        track = tracks[idx] if 0 <= idx < len(tracks) else None
        if track is None or track.lyrics_path is None:
            set_lyrics([])
            return
        set_lyrics(load_lyrics(track.lyrics_path))

    ft.use_effect(refresh_lyrics, [current, selected, tracks])

    def on_brightness_change(e: ft.ControlEvent) -> None:
        page.theme_mode = (
            ft.ThemeMode.DARK
            if page.platform_brightness == "dark"
            else ft.ThemeMode.LIGHT
        )
        page.update()

    page.on_platform_brightness_change = on_brightness_change

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
        await apply_tracks(files)

    async def on_toggle(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.toggle()

    def bind_keyboard() -> None:
        async def on_keyboard(e: ft.KeyboardEvent) -> None:
            if e.key != " " or e.ctrl or e.alt or e.meta:
                return
            if search_focused_ref.current:
                return
            if player_ref.current:
                await player_ref.current.toggle()

        page.on_keyboard_event = on_keyboard

    ft.use_effect(bind_keyboard, dependencies=[])

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

    def on_select(track: Track) -> None:
        try:
            index = tracks.index(track)
        except ValueError:
            return
        set_selected(index)

    async def on_play(track: Track) -> None:
        try:
            index = tracks.index(track)
        except ValueError:
            return
        if player_ref.current:
            await player_ref.current.play_at(index)
        set_selected(index)

    async def on_favorite(track: Track) -> None:
        key = track_key(track.path)
        track.favorite = not track.favorite
        if track.favorite:
            favorites_ref.current.add(key)
        else:
            favorites_ref.current.discard(key)
        await save_favorites(page.shared_preferences, favorites_ref.current)
        set_tracks([*tracks])

    async def on_seek(seconds: float) -> None:
        if player_ref.current:
            await player_ref.current.seek(seconds)
            set_position(seconds)

    def on_search_focus() -> None:
        search_focused_ref.current = True

    def on_search_blur() -> None:
        search_focused_ref.current = False

    playing_track = tracks[current] if 0 <= current < len(tracks) else None
    display_index = current if current >= 0 else selected
    track = tracks[display_index] if 0 <= display_index < len(tracks) else None
    has_lyrics = bool(track and track.lyrics_path)
    playlist_count = len(tracks)

    filtered_tracks = [
        t
        for t in tracks
        if (not show_favorites or t.favorite)
        and (
            not search
            or search.lower() in t.title.lower()
            or search.lower() in t.path.parent.name.lower()
        )
    ]
    filtered_selected = (
        next(
            (i for i, t in enumerate(filtered_tracks) if t is tracks[selected]),
            -1,
        )
        if 0 <= selected < len(tracks)
        else -1
    )

    toolbar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.LIBRARY_MUSIC, color=SURFACE, size=20
                            ),
                            width=36,
                            height=36,
                            alignment=ft.Alignment.CENTER,
                            bgcolor=PRIMARY,
                            border_radius=10,
                        ),
                        ft.Text(
                            "CS 音乐播放器",
                            size=16,
                            weight=ft.FontWeight.W_700,
                            color=TEXT_MAIN,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(expand=True),
                ft.Text(
                    "正在播放" if is_playing and track else "",
                    size=12,
                    color=TEXT_DIM,
                    italic=True,
                ),
                ft.Button(
                    content="导入音乐",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=on_import,
                    style=ft.ButtonStyle(
                        bgcolor={
                            ft.ControlState.DEFAULT: PRIMARY,
                            ft.ControlState.HOVERED: PRIMARY_DARK,
                        },
                        color=ft.Colors.WHITE,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, "#dbe3ee")),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
    )

    return ft.Container(
        expand=True,
        bgcolor=BG,
        content=ft.Column(
            [
                toolbar,
                ft.Row(
                    [
                        Sidebar(
                            filtered_tracks,
                            filtered_selected,
                            playing_track,
                            search,
                            show_favorites,
                            playlist_count,
                            set_search,
                            set_show_favorites,
                            on_select,
                            on_play,
                            on_favorite,
                            is_playing,
                            on_search_focus,
                            on_search_blur,
                        ),
                        MainStage(track, is_playing, lyrics, position, has_lyrics),
                    ],
                    expand=True,
                    spacing=0,
                ),
                PlayerBar(
                    track,
                    is_playing,
                    position,
                    duration,
                    volume,
                    mode,
                    dragging,
                    on_toggle,
                    on_prev,
                    on_next,
                    on_mode,
                    on_seek,
                    on_volume,
                ),
            ],
            spacing=0,
            expand=True,
        ),
    )
