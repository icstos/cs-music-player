"""顶层应用组件：集中持有 UI 状态，组装布局，桥接播放器与视图。"""

from __future__ import annotations

import asyncio
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
    ACCENT,
    BORDER,
    BG,
    MODE_SEQUENCE,
    PRIMARY,
    PRIMARY_DARK,
    SURFACE,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_MUTED,
)
from .lrclib import download_lyrics
from .lyrics import load_lyrics
from .store import (
    apply_favorites,
    load_favorites,
    load_pinned_folders,
    load_recent_folders,
    normalize_folder_path,
    push_recent_folder,
    save_favorites,
    save_pinned_folders,
    save_recent_folders,
    toggle_pinned_folder,
    track_key,
)
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
    recent_folders, set_recent_folders = ft.use_state(list[str]())
    pinned_folders, set_pinned_folders = ft.use_state(set[str]())

    dragging = ft.use_ref(False)
    player_ref = ft.use_ref(None)
    picker_ref = ft.use_ref(None)
    prefs_ref = ft.use_ref(None)
    favorites_ref = ft.use_ref(set[str]())
    search_focused_ref = ft.use_ref(False)
    lyric_downloads_ref = ft.use_ref(set[str]())
    folder_menu_ref = ft.use_ref(None)

    def sync_track_state(index: int) -> None:
        set_current(index)
        set_selected(index)

    async def load_recent_folder_state() -> None:
        prefs = get_prefs()
        folders = await load_recent_folders(prefs)
        pinned = await load_pinned_folders(prefs)
        set_recent_folders(folders)
        set_pinned_folders(pinned)

    async def ensure_lyrics(track: Track) -> None:
        """曲目缺少本地歌词时，后台从 LRCLIB 下载并回填。"""
        player = player_ref.current
        if player is None or track.lyrics_path is not None:
            return
        key = str(track.path.resolve())
        if key in lyric_downloads_ref.current:
            return
        lyric_downloads_ref.current.add(key)
        try:
            path = await download_lyrics(track)
            if path is not None:
                track.lyrics_path = path
                if (
                    player.current >= 0
                    and player.tracks[player.current] is track
                ):
                    set_lyrics(load_lyrics(path))
        finally:
            lyric_downloads_ref.current.discard(key)

    def on_track_change(index: int) -> None:
        sync_track_state(index)
        player = player_ref.current
        if player is not None and 0 <= index < len(player.tracks):
            asyncio.create_task(ensure_lyrics(player.tracks[index]))

    def setup() -> None:
        player_ref.current = Player(
            PlayerCallbacks(
                on_position=set_position,
                on_duration=set_duration,
                on_play_state=set_is_playing,
                on_track_change=on_track_change,
            ),
            page,
        )
        prefs_ref.current = ft.SharedPreferences()
        page.services.append(prefs_ref.current)
        picker = ft.FilePicker()
        page.services.append(picker)
        page.update()
        picker_ref.current = picker

    def get_prefs() -> ft.SharedPreferences:
        if prefs_ref.current is None:
            prefs_ref.current = ft.SharedPreferences()
        return prefs_ref.current

    ft.use_effect(setup, dependencies=[])

    async def apply_tracks(
        files: list[Track],
        *,
        play_index: int = 0,
        autoplay: bool = False,
        source_folder: Path | None = None,
    ) -> None:
        favorites_ref.current = await load_favorites(get_prefs())
        apply_favorites(files, favorites_ref.current)
        player = player_ref.current
        if player:
            player.set_tracks(files)
            if autoplay and 0 <= play_index < len(files):
                await player.play_at(play_index)
        set_tracks(files)
        set_selected(play_index if files else -1)
        if source_folder is not None:
            prefs = get_prefs()
            folders = push_recent_folder(
                await load_recent_folders(prefs),
                str(source_folder),
            )
            await save_recent_folders(prefs, folders)
            set_recent_folders(folders)
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
        async def run() -> None:
            await load_recent_folder_state()
            if not startup_path:
                return
            load = resolve_startup_load(Path(startup_path))
            if load is None:
                return
            await apply_tracks(
                load.tracks,
                play_index=load.play_index,
                autoplay=load.autoplay,
                source_folder=Path(startup_path).parent if Path(startup_path).is_file() else Path(startup_path),
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
        path = Path(directory)
        files = load_tracks_from_directory(path)
        if not files:
            return
        await apply_tracks(files, source_folder=path)

    async def open_recent_folder(folder: str) -> None:
        path = Path(folder)
        if not path.exists() or not path.is_dir():
            notify("历史文件夹已不存在")
            return
        files = load_tracks_from_directory(path)
        if not files:
            notify("该文件夹没有可播放的音乐")
            return
        await apply_tracks(files, source_folder=path)
        notify(f"已打开：{path.name or path}")

    async def toggle_pin_folder(folder: str) -> None:
        """固定 / 取消固定某个文件夹，并持久化。"""
        pinned = toggle_pinned_folder(set(pinned_folders), folder)
        await save_pinned_folders(get_prefs(), pinned)
        set_pinned_folders(pinned)

    async def clear_recent_history() -> None:
        """清空最近打开记录，保留固定文件夹。"""
        await save_recent_folders(get_prefs(), [])
        set_recent_folders([])
        notify("已清空历史记录")

    def notify(message: str) -> None:
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message),
                behavior=ft.SnackBarBehavior.FLOATING,
                margin=ft.Margin.only(left=16, right=16, bottom=16),
                duration=ft.Duration(milliseconds=2200),
                bgcolor=SURFACE,
            )
        )

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
        # 仅更新选中项，不改变正在播放的曲目
        set_selected(index)

    async def on_play(track: Track) -> None:
        try:
            index = tracks.index(track)
        except ValueError:
            return
        if player_ref.current:
            await player_ref.current.play_at(index)
        # play_at 内部已通过 on_track_change 同步 current/selected

    async def on_favorite(track: Track) -> None:
        key = track_key(track.path)
        track.favorite = not track.favorite
        if track.favorite:
            favorites_ref.current.add(key)
        else:
            favorites_ref.current.discard(key)
        await save_favorites(get_prefs(), favorites_ref.current)
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
            or search.lower() in t.artist.lower()
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

    def build_folder_item(folder: str, pinned: bool) -> ft.PopupMenuItem:
        path = Path(folder)
        name = path.name or folder
        return ft.PopupMenuItem(
            tooltip=folder,
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.PUSH_PIN if pinned else ft.Icons.FOLDER_OPEN,
                        size=15,
                        color=ACCENT if pinned else PRIMARY_DARK,
                    ),
                    ft.Text(
                        name,
                        size=12,
                        color=TEXT_MAIN,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=(
                            ft.Icons.PUSH_PIN_OUTLINED
                            if not pinned
                            else ft.Icons.PUSH_PIN
                        ),
                        icon_size=14,
                        icon_color=ACCENT if pinned else TEXT_MUTED,
                        tooltip="取消固定" if pinned else "固定文件夹",
                        on_click=lambda e, f=folder: asyncio.create_task(
                            toggle_pin_folder(f)
                        ),
                        padding=ft.Padding.all(2),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e, f=folder: asyncio.create_task(open_recent_folder(f)),
        )

    def build_section_header(text: str) -> ft.PopupMenuItem:
        return ft.PopupMenuItem(
            content=ft.Text(
                text,
                size=11,
                weight=ft.FontWeight.W_600,
                color=TEXT_MUTED,
            ),
            height=32,
        )

    recent_items: list[ft.PopupMenuItem] = []
    pinned_set = set(pinned_folders)
    pinned_list = [
        f for f in recent_folders if f in pinned_set
    ] + [
        f for f in sorted(pinned_set) if f not in recent_folders
    ]
    recent_list = [f for f in recent_folders if f not in pinned_set]
    if pinned_list:
        recent_items.append(build_section_header("固定文件夹"))
        recent_items.extend(build_folder_item(f, True) for f in pinned_list)
        if recent_list:
            recent_items.append(
                ft.PopupMenuItem(
                    content=ft.Divider(height=1, color=BORDER),
                    height=1,
                )
            )
    if recent_list:
        recent_items.append(build_section_header("最近打开"))
        recent_items.extend(build_folder_item(f, False) for f in recent_list)
    if not pinned_list and not recent_list:
        recent_items.append(
            ft.PopupMenuItem(
                content=ft.Text("暂无历史文件夹", size=12, color=TEXT_MUTED),
                on_click=lambda e: None,
            )
        )
    elif recent_list:
        recent_items.append(
            ft.PopupMenuItem(
                content=ft.Divider(height=1, color=BORDER),
                height=1,
            )
        )
        recent_items.append(
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.DELETE_OUTLINE, size=15, color=TEXT_MUTED),
                        ft.Text("清空历史", size=12, color=TEXT_DIM),
                    ],
                    spacing=8,
                ),
                on_click=lambda e: asyncio.create_task(clear_recent_history()),
            )
        )

    menu_width = 300

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
                ft.PopupMenuButton(
                    icon=ft.Icons.HISTORY,
                    icon_color=PRIMARY_DARK,
                    icon_size=22,
                    tooltip="历史文件夹",
                    style=ft.ButtonStyle(padding=ft.Padding.all(8)),
                    menu_position=ft.PopupMenuPosition.UNDER,
                    size_constraints=ft.BoxConstraints(
                        min_width=menu_width, max_width=menu_width
                    ),
                    items=recent_items,
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
