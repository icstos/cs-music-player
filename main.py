"""CS Music Player 入口。"""

import flet as ft

from cs_music_player.app import PlayerApp
from cs_music_player.constants import BG, PRIMARY


def main(page: ft.Page) -> None:
    page.title = "CS 音乐播放器"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=PRIMARY)
    page.bgcolor = BG
    page.window.min_width = 900
    page.window.min_height = 640
    page.window.width = 1180
    page.window.height = 780
    page.window.resizable = True
    page.window.maximizable = True
    page.padding = 0
    page.render(PlayerApp, page)


if __name__ == "__main__":
    ft.run(main)
