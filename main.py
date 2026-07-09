"""CS Music Player 入口。"""

import flet as ft

from cs_music_player.app import PlayerApp
from cs_music_player.constants import BG_COLOR


def main(page: ft.Page) -> None:
    page.title = "CS 音乐播放器"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_PURPLE)
    page.bgcolor = BG_COLOR
    page.window.width = 1000
    page.window.height = 720
    page.window.min_width = 760
    page.window.min_height = 600
    page.padding = 24
    page.render(PlayerApp, page)


if __name__ == "__main__":
    ft.run(main)
