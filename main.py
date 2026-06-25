import flet as ft
from flet_audio import Audio
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import asyncio


class MusicPlayer:
    def __init__(self):
        self.songs = []
        self.current_song_index = -1
        self.is_playing = False
        self.current_position = 0
        self.duration = 0


def main(page: ft.Page):
    page.title = "音乐播放器"
    page.window.width = 1000
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.DEEP_PURPLE,
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
    page.padding = 20

    player = MusicPlayer()
    audio = None

    current_song_text = ft.Text(
        "未选择歌曲",
        size=20,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.WHITE,
        text_align=ft.TextAlign.CENTER,
    )

    current_song_path = ft.Text(
        "", size=12, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER
    )

    progress_bar = ft.Slider(
        min=0,
        max=100,
        value=0,
        width=600,
        active_color=ft.Colors.DEEP_PURPLE,
        thumb_color=ft.Colors.DEEP_PURPLE_400,
    )

    time_text = ft.Text("0:00 / 0:00", size=14, color=ft.Colors.GREY_300)

    volume_slider = ft.Slider(
        min=0,
        max=100,
        value=70,
        width=150,
        active_color=ft.Colors.BLUE,
        thumb_color=ft.Colors.BLUE_400,
    )

    song_list = ft.ListView(width=950, height=400, spacing=5, padding=10)

    play_pause_icon = ft.IconButton(
        icon=ft.Icons.PLAY_CIRCLE,
        icon_color=ft.Colors.WHITE,
        icon_size=50,
        tooltip="播放/暂停",
    )

    volume_icon = ft.Icon(icon=ft.Icons.VOLUME_UP, color=ft.Colors.BLUE_400, size=24)

    def format_time(seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def update_time_display():
        current = format_time(player.current_position)
        total = format_time(player.duration)
        time_text.value = f"{current} / {total}"

    def on_duration_changed(e):
        player.duration = e.data / 1000
        update_time_display()
        page.update()

    def on_position_changed(e):
        player.current_position = e.data / 1000
        if player.duration > 0:
            progress = (player.current_position / player.duration) * 100
            progress_bar.value = progress
        update_time_display()
        page.update()

    async def on_state_changed(e):
        if e.data == "completed":
            await on_next_click(None)

    def init_audio():
        nonlocal audio
        audio = Audio(
            src="",
            autoplay=False,
            volume=0.7,
            on_duration_change=on_duration_changed,
            on_position_change=on_position_changed,
            on_state_change=on_state_changed,
        )
        page.overlay.append(audio)
        page.update()

    def update_song_list():
        song_list.controls.clear()
        for i, song in enumerate(player.songs):
            song_name = song.stem
            song_item = ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.MUSIC_NOTE,
                        color=ft.Colors.DEEP_PURPLE_400
                        if i == player.current_song_index
                        else ft.Colors.GREY_400,
                    ),
                    title=ft.Text(
                        song_name,
                        color=ft.Colors.WHITE
                        if i == player.current_song_index
                        else ft.Colors.GREY_300,
                        weight=ft.FontWeight.BOLD
                        if i == player.current_song_index
                        else ft.FontWeight.NORMAL,
                    ),
                    subtitle=ft.Text(
                        str(song),
                        color=ft.Colors.GREY_500,
                        size=11,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    on_click=lambda e, idx=i: asyncio.create_task(
                        play_selected_song(idx)
                    ),
                ),
                bgcolor=ft.Colors.DEEP_PURPLE_900
                if i == player.current_song_index
                else ft.Colors.TRANSPARENT,
                border_radius=8,
                padding=5,
            )
            song_list.controls.append(song_item)
        page.update()

    async def play_selected_song(index):
        if audio is None:
            return
        if 0 <= index < len(player.songs):
            player.current_song_index = index
            song_path = str(player.songs[index])
            audio.src = song_path
            try:
                await audio.play()
                player.is_playing = True
                play_pause_icon.icon = ft.Icons.PAUSE_CIRCLE
                current_song_text.value = player.songs[index].stem
                current_song_path.value = str(player.songs[index])
                update_song_list()
            except Exception as ex:
                print(f"播放错误: {ex}")

    async def on_play_pause(e):
        if audio is None or player.current_song_index < 0:
            return
        if player.is_playing:
            await audio.pause()
            player.is_playing = False
            play_pause_icon.icon = ft.Icons.PLAY_CIRCLE
        else:
            await audio.resume()
            player.is_playing = True
            play_pause_icon.icon = ft.Icons.PAUSE_CIRCLE
        page.update()

    async def on_previous(e):
        if player.songs and player.current_song_index >= 0:
            prev_index = (player.current_song_index - 1) % len(player.songs)
            await play_selected_song(prev_index)

    async def on_next_click(e):
        if player.songs and player.current_song_index >= 0:
            next_index = (player.current_song_index + 1) % len(player.songs)
            await play_selected_song(next_index)

    def on_volume_change(e):
        if audio is None:
            return
        volume = volume_slider.value / 100
        audio.volume = volume
        if volume == 0:
            volume_icon.icon = ft.Icons.VOLUME_MUTE
        elif volume < 0.5:
            volume_icon.icon = ft.Icons.VOLUME_DOWN
        else:
            volume_icon.icon = ft.Icons.VOLUME_UP
        page.update()

    async def on_progress_change(e):
        if audio is None or player.duration <= 0:
            return
        new_position_ms = int((progress_bar.value / 100) * player.duration * 1000)
        await audio.seek(new_position_ms)

    def load_music(e):
        root = tk.Tk()
        root.withdraw()
        directory = filedialog.askdirectory(title="选择音乐文件夹")
        if directory:
            player.songs = []
            music_dir = Path(directory)
            if music_dir.exists() and music_dir.is_dir():
                supported_formats = [".mp3", ".wav", ".ogg", ".flac", ".m4a"]
                for file in music_dir.iterdir():
                    if file.is_file() and file.suffix.lower() in supported_formats:
                        player.songs.append(file)
            update_song_list()

    play_pause_icon.on_click = lambda e: asyncio.create_task(on_play_pause(e))
    volume_slider.on_change = on_volume_change
    progress_bar.on_change = lambda e: asyncio.create_task(on_progress_change(e))

    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.LIBRARY_MUSIC, color=ft.Colors.DEEP_PURPLE_400, size=32
                ),
                ft.Text(
                    "音乐播放器",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                ft.Container(expand=True),
                ft.Button(
                    "选择音乐文件夹",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=load_music,
                    bgcolor=ft.Colors.DEEP_PURPLE_600,
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=20, vertical=12)
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=20,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.DEEP_PURPLE),
        border_radius=12,
    )

    player_info = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.ALBUM, size=120, color=ft.Colors.DEEP_PURPLE_400
                    ),
                    alignment=ft.alignment.Alignment(0.5, 0.5),
                    margin=ft.Margin.only(bottom=20),
                ),
                current_song_text,
                current_song_path,
                ft.Container(height=20),
                ft.Row(
                    controls=[
                        ft.Container(expand=True),
                        progress_bar,
                        ft.Container(expand=True),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    controls=[
                        ft.Container(expand=True),
                        time_text,
                        ft.Container(expand=True),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=30,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.DEEP_PURPLE),
        border_radius=12,
        margin=ft.Margin.only(top=20),
    )

    controls = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.SKIP_PREVIOUS,
                    icon_color=ft.Colors.WHITE,
                    icon_size=36,
                    tooltip="上一曲",
                    on_click=lambda e: asyncio.create_task(on_previous(e)),
                ),
                play_pause_icon,
                ft.IconButton(
                    icon=ft.Icons.SKIP_NEXT,
                    icon_color=ft.Colors.WHITE,
                    icon_size=36,
                    tooltip="下一曲",
                    on_click=lambda e: asyncio.create_task(on_next_click(e)),
                ),
                ft.VerticalDivider(color=ft.Colors.GREY_700, width=40),
                volume_icon,
                volume_slider,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
        padding=20,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.DEEP_PURPLE),
        border_radius=12,
        margin=ft.Margin.only(top=20),
    )

    song_list_container = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "播放列表",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    margin=ft.Margin.only(bottom=10),
                ),
                song_list,
            ],
            alignment=ft.MainAxisAlignment.START,
        ),
        padding=20,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.DEEP_PURPLE),
        border_radius=12,
        margin=ft.Margin.only(top=20),
    )

    layout = ft.Column(
        controls=[header, player_info, controls, song_list_container],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
    )

    page.add(layout)

    def on_page_connect(e):
        init_audio()

    page.on_connect = on_page_connect


if __name__ == "__main__":
    ft.run(main)
