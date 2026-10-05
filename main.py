"""CS Music Player 入口。

「进程启动 → 窗口可见」这条路上，去掉 Python 自身的启动时间后，真正省不掉的
只有三件事：``import flet``、``ft.run`` 里导入消息层、以及拉起客户端进程。
剩下两块一次性开销则可以藏起来，实测约占 140ms：

- 业务模块导入（连带 flet_audio）≈ 43ms；
- 首次 ``ft.Theme(...)`` 构造 ≈ 96ms——flet 把 ``flet.controls.theme`` 藏在包
  的 ``__getattr__`` 后面惰性导入，一上来要加载 58 个模块。

桌面端外壳被拉起后，约 140ms 才回连注册、再约 90ms 才画出第一帧；这段时间
Python 侧本来在空转（主线程正 ``await`` 客户端进程，GIL 是空的，后台线程能
全速跑）。于是这里挂一个钩子，外壳一被拉起就在后台线程里把上面两块预热掉，
等 ``before_main`` / ``main`` 真要用时基本都是现成的：``before_main``
由 73ms 降到 14ms。实测「进程启动 → 窗口可见」由 0.68s 降到 0.60s（六轮
交替对比，6/6 更快）。

反过来，把这两块放进后台线程**并行导入**是没有意义的：模块导入是 GIL 绑定
的，实测并行反而略慢（socket 层与 flet_desktop 串行 207ms，并行 220ms+）。

窗口参数仍然必须在注册阶段（``before_main``）就定下来：外壳会先用默认尺寸
（1280×720）、默认位置建窗，晚设就会「左上角闪一下再跳尺寸」。
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import suppress

import flet as ft

from cs_music_player.startup import parse_startup_path

STARTUP_PATH = parse_startup_path()

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 780
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640

# 等待客户端「可以显示窗口」的上限：正常远低于此值，
# 仅用于避免极端情况下窗口一直不出现。
REVEAL_TIMEOUT = 5.0


def prewarm() -> None:
    """导入业务模块并构造一次主题。

    两块都是纯粹的一次性开销（模块导入 + flet 的惰性导入），提前做掉不改变
    任何运行期行为；重复调用也无副作用（``sys.modules`` 已缓存，主题构造在
    热态只要 0.01ms）。
    """

    from cs_music_player import constants as constants_module
    from cs_music_player.app import PlayerApp  # noqa: F401  仅为预热导入

    constants_module.build_light_theme()
    constants_module.build_dark_theme()


def install_prewarm_hook() -> bool:
    """把「客户端被拉起」变成一个可以挂预热动作的通知点。

    flet 在 ``flet.app.run_async`` 里才 ``from flet_desktop import
    open_flet_view_async``，所以只要在那之前把模块属性换掉就能包住它。
    返回是否挂上了。
    """

    try:
        import flet_desktop

        original = flet_desktop.open_flet_view_async

        async def open_flet_view_async_with_prewarm(*args, **kwargs):
            view = await original(*args, **kwargs)
            # 此刻外壳进程已经起来、正在初始化 Flutter，而 Python 侧要等它
            # 回连才会被回调——正是预热的好时机。
            threading.Thread(
                target=prewarm, name="flet-prewarm", daemon=True
            ).start()
            return view

        flet_desktop.open_flet_view_async = open_flet_view_async_with_prewarm
        return True
    except Exception:
        return False


HOOK_INSTALLED = install_prewarm_hook()


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

    实测（见 .workbuddy/probe/phase_wrap.py）：这样改完后窗口只出现一次，
    且首次出现的画面就是完整界面，不再有 1280×720 的空白窗口一闪。
    """

    if not HOOK_INSTALLED:
        # 钩子没挂上时兜底：惰性导入的一次性开销必须现在付掉，
        # 否则它会算进「注册补丁晚发」的时间里。
        prewarm()

    from cs_music_player.constants import (
        FONT_FAMILY,
        FONT_FAMILY_FILE,
        build_dark_theme,
        build_light_theme,
        palette,
    )

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
    from cs_music_player.app import PlayerApp

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
