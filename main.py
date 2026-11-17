"""CS Music Player 入口。

「进程启动 → 窗口可见」这条路上，去掉 Python 自身的启动时间后，真正省不掉的
只有三件事：``import flet``（``import ui`` 会带上它）、``ft.run`` 里导入消息层、
以及拉起客户端进程。剩下两块一次性开销则可以藏起来，实测约省 140ms：

- 业务模块导入（连带 flet_audio）≈ 43ms；
- 首次 ``ft.Theme(...)`` 构造 ≈ 96ms——flet 把 ``flet.controls.theme`` 藏在包级
  的 ``__getattr__`` 后面惰性导入，一上来要加载 58 个模块。

桌面端外壳被拉起后，约 140ms 才回连注册、再约 90ms 才画出第一帧；这段时间
Python 侧本来在空转（主线程止于 ``await`` 客户端进程，GIL 是空的，后台线程能
全速跑）。于是这里挂一个钩子，外壳一被拉起就在后台线程里把上面两块预热掉，
等 ``before_main`` / ``main`` 真要用时基本都是现成的：``before_main``
由 73ms 降到 14ms。实测「进程启动 → 窗口可见」由 0.68s 降到 0.60s。

反过来，把这两块放进后台线程**并行导入**是没有意义的：模块导入是 GIL 绑定
的，实测并行反而略慢。

窗口参数仍然必须在注册阶段（``before_main``）就定下来：外壳会先用默认尺寸
（1280×720）、默认位置建窗，晚设就会「左上角闪一下再跳尺寸」。

主题也在这里先铺一遍：窗口显示前就有一棵完整的主题树，首帧不会先白一下再
变成深色。这里**只用** ``ui.build_theme`` 造两棵树，不用 ``apply_theme`` ——
后者会顺手绑系统亮度监听，而那个监听要等视图模型建好后才能绑上回调。
"""

from __future__ import annotations

import asyncio
import sys
import threading
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

# src 布局必需：隔离打包环境（serious_python / PyInstaller 等）不会执行
# pip install -e .，包被编译到 <app>/src/cs_music_player/，而运行时 sys.path
# 只有 <app>/ 根、不含 src。这段同时覆盖开发态与打包态，删掉即打包后
# ModuleNotFoundError。用 __file__ 而非 cwd，因为打包后 cwd 不确定。
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path and (_SRC / "cs_music_player").exists():
    sys.path.insert(0, str(_SRC))

from cs_music_player.infra.startup_args import parse_startup_path  # noqa: E402

if TYPE_CHECKING:  # 只为类型注解；运行期不导入 ui，启动路径保持最短
    from ui import ft

STARTUP_PATH = parse_startup_path()

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 780
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 640

#: 等待客户端「可以显示窗口」的上限：正常远低于此值，
#: 仅用于避免极端情况下窗口一直不出现。
REVEAL_TIMEOUT = 5.0


def prewarm() -> None:
    """导入业务模块，并把明暗两棵主题树先造出来。

    两块都是纯补的一次性开销（模块导入 + flet 的惰性导入），提前做掉不改变
    任何运行期行为；重复调用也无副作用（``sys.modules`` 已缓存，主题构造在
    热态只要 0.01ms）。
    """

    from ui import build_theme, theme_state

    from cs_music_player.bootstrap import build_view_model  # noqa: F401  预热导入
    from cs_music_player.models import FONT_FAMILY

    state = theme_state()
    state.font_family = FONT_FAMILY
    state.set_primary(_initial_seed())
    build_theme(state, "light")
    build_theme(state, "dark")


def install_prewarm_hook() -> bool:
    """把「客户端被拉起」变成一个可以挂预热动作的通知点。

    flet 在 ``flet.app.run_async`` 里才 ``from flet_desktop import
    open_flet_view_async``，所以只要在那之前把模块属性换掉就能包住它。
    返回是否挂上了。
    """

    try:
        import flet_desktop

        original = flet_desktop.open_flet_view_async

        async def open_flet_view_async_with_prewarm(
            *args: Any, **kwargs: Any
        ) -> Any:
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
    """在客户端注册阶段（窗口尚未显示）就把窗口与主题定下来。

    桌面端外壳会先用默认尺寸（1280×720）、默认位置（屏幕左上角）建一个窗口，
    等 Python 端连上才改成目标尺寸。若这时窗口已经可见，用户看到的就是
    「左上角闪一下、再跳成正常窗口」。

    因此这里做三件事：

    1. 写下明暗两套主题与页面底色 —— 客户端按 ``theme_mode`` 挑一棵现成的树，
       首帧就是正确的配色，不需要等 Python 重算；
    2. ``visible = False`` —— 窗口先不露出，等首帧内容画好再由
       :func:`reveal_window` 一次性显示；
    3. 立刻填一个与主题同色的占位页 —— 客户端在「还没有页面」时会先画出白底
       Flet logo 的等待页，显示瞬间可能露出 1~3 帧。
    """

    if not HOOK_INSTALLED:
        # 钩子没挂上时兜底：惰性导入的一次性开销必须现在付掉，
        # 否则它会算进「注册补丁晚发」的时间里。
        prewarm()

    from ui import build_theme, ft, theme_state

    from cs_music_player.models import FONT_FAMILY, FONT_FAMILY_FILE

    state = theme_state()
    state.font_family = FONT_FAMILY
    state.set_primary(_initial_seed())
    state.set_mode("light")

    page.title = "CS 音乐播放器"
    page.fonts = {FONT_FAMILY: FONT_FAMILY_FILE}
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = build_theme(state, "light")
    page.dark_theme = build_theme(state, "dark")
    page.bgcolor = ft.Colors.SURFACE
    page.padding = 0

    page.window.visible = False
    page.window.min_width = WINDOW_MIN_WIDTH
    page.window.min_height = WINDOW_MIN_HEIGHT
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.resizable = True
    page.window.maximizable = True

    page.controls = [ft.Container(bgcolor=ft.Colors.SURFACE, expand=True)]


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
    from cs_music_player.bootstrap import run_app

    try:
        await run_app(page, STARTUP_PATH)
    finally:
        # 即使渲染出错也要把窗口显示出来，否则用户只会看到「程序没反应」。
        await reveal_window(page)


def _initial_seed() -> str:
    """启动配色：用户没切过主题时就是它，切过也会在第一帧之后被换掉。"""
    from cs_music_player.models import DEFAULT_THEME_SEED

    return DEFAULT_THEME_SEED


if __name__ == "__main__":
    from ui import ft

    ft.run(
        main,
        before_main=configure_window,
        view=ft.AppView.FLET_APP_HIDDEN,
        assets_dir="assets",
    )
