"""CS Music Player 入口。"""

import asyncio
from contextlib import suppress

import flet as ft

from cs_music_player.app import PlayerApp
from cs_music_player.constants import (
    FONT_FAMILY,
    FONT_FAMILY_FILE,
    build_dark_theme,
    build_light_theme,
    palette,
)
from cs_music_player.startup import parse_startup_path

STARTUP_PATH = parse_startup_path()

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 780
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640

# 等待客户端「可以显示窗口」的上限：正常远低于此值，
# 仅用于避免极端情况下窗口一直不出现。
REVEAL_TIMEOUT = 5.0


def configure_window(page: ft.Page) -> None:
    """在客户端注册阶段（窗口尚未显示）就把窗口参数定下来。

    桌面端外壳会先用默认尺寸（1280×720）、默认位置（屏幕左上角）建一个窗口，
    等 Python 端连上才改成目标尺寸。若这时窗口已经可见，用户看到的就是
    「左上角闪一下、再跳成正常窗口」。
    因此这里做两件事：

    1. ``visible = False`` —— 窗口先不露出，等首帧内容画好再由
       :func:`reveal_window` 一次性显示；
    2. 立刻塞一个与主题同色的占位页 —— 客户端在「还没有页面」时会先画出白底
       Flet logo 的等待页，显示瞬间可能露出 1~3 帧；有占位页时实测 4/5 次
       首帧就是完整界面。

    实测（见 .workbuddy/probe/window_flash_probe.py）：这样改完后窗口只出现
    一次，且首次出现的画面就是完整界面，不再有 1280×720 的空白窗口一闪。
    """

    page.title = "CS 音乐播放器"
    page.fonts = {FONT_FAMILY: FONT_FAMILY_FILE}
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = build_light_theme()
    page.dark_theme = build_dark_theme()
    page.bgcolor = palette.BG
    page.padding = 0

    page.window.visible = False
    page.window.min_width = WINDOW_MIN_WIDTH
    page.window.min_height = WINDOW_MIN_HEIGHT
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.resizable = True
    page.window.maximizable = True

    page.controls = [ft.Container(bgcolor=palette.BG, expand=True)]


async def reveal_window(page: ft.Page) -> None:
    """首帧内容渲染完成后，一次性把窗口显示出来。"""

    # 让客户端确认「首帧已画好」，避免窗口先于内容露出来（白屏一闪）。
    with suppress(Exception):
        await asyncio.wait_for(
            page.window.wait_until_ready_to_show(), REVEAL_TIMEOUT
        )

    page.window.visible = True
    page.update()


async def main(page: ft.Page) -> None:
    try:
        page.render(
            PlayerApp,
            page,
            str(STARTUP_PATH) if STARTUP_PATH else None,
        )
    finally:
        # 即使渲染出错也要把窗口显示出来，否则用户只会看到「程序没反应」。
        await reveal_window(page)


if __name__ == "__main__":
    ft.run(
        main,
        before_main=configure_window,
        view=ft.AppView.FLET_APP_HIDDEN,
        assets_dir="assets",
    )
