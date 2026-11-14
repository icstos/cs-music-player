"""视图层根组件：把视图模型的状态声明式地渲染成界面。

本模块是**纯视图**：不导入 service / infra，不做业务流程，只做两件事——

1. 读 :class:`~cs_music_player.viewmodel.app.AppViewModel` 的状态，构造控件树；
2. 把用户操作转成视图模型的方法调用。

状态变化由视图模型广播，本组件订阅后重渲染，因此「UI = f(状态)」。

界面**只依赖 ``ui``（cs-ui 组件库）**：布局用 ``Container`` / ``Row`` / ``Column`` /
``ListView``，控件用 ``Button`` / ``IconButton`` / ``PopupMenuButton``，连颜色与对齐这类
值类型也从 ``ui`` 顶层取（``Colors`` / ``Alignment`` / ``Padding``…）。因此本包里看不到
任何 flet 前缀——唯一的例外是 :mod:`cs_music_player.view.components.primitives`
（cs-ui 的同名控件是表单组件，与这里的「裸滑轨」同名不同物）。
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from ui import (
    Alignment,
    Border,
    BorderSide,
    BoxConstraints,
    Button,
    ButtonStyle,
    Colors,
    Column,
    Container,
    Control,
    CrossAxisAlignment,
    Divider,
    FontWeight,
    Icon,
    IconButton,
    Icons,
    KeyboardEvent,
    Message,
    Padding,
    Page,
    PopupMenuButton,
    PopupMenuItem,
    PopupMenuPosition,
    Row,
    SPACE,
    StyleType,
    Text,
    TextOverflow,
    component,
    use_effect,
    use_ref,
    use_state,
)

from ..models import ThemeMode
from ..viewmodel import AppViewModel
from . import tokens as t
from .components import (
    DesktopLyricButton,
    MainStage,
    PlayerBar,
    Sidebar,
    SleepTimerButton,
    ThemeMenuButton,
    build_sleep_dialog,
)
from .theme import sync_theme

__all__ = ["PlayerApp", "build_history_menu"]

#: 顶栏高度：与「导入音乐」按钮（36）上下各留 12 的呼吸。
TOOLBAR_PAD_Y = SPACE["3"]


@component
def PlayerApp(
    page: Page,
    vm: AppViewModel,
    on_appearance: Callable[[bool], None] | None = None,
) -> Control:
    """应用主界面。

    Args:
        page: 页面。
        vm: 视图模型。
        on_appearance: 明暗切换后的旁路回调（参数为「是否深色」）。原生标题栏
            这类**不属于 Flutter 画布**的东西由组装根注入，视图只负责「什么时候
            通知」，不碰任何平台细节。
    """
    # 视图模型是不可变数据源；用一个自增版本号驱动整棵树重渲染。
    revision, set_revision = use_state(0)
    invalidate = use_ref(lambda: None)
    dragging = use_ref(False)
    search_focused = use_ref(False)
    sleep_dialog = use_ref(None)

    def bump_revision() -> None:
        set_revision(lambda value: value + 1)

    invalidate.current = bump_revision

    def on_state_changed() -> None:
        """视图模型变了：重渲染整棵树。"""
        invalidate.current()

    use_effect(lambda: vm.subscribe(on_state_changed), [vm])

    # —— 主题：配色 / 明暗变了才重下发页面级主题 —— #
    color_theme = vm.color_theme
    theme_mode = vm.theme_mode

    def push_theme() -> None:
        sync_theme(
            page,
            color_theme,
            theme_mode,
            on_brightness=vm.set_system_brightness,
        )
        if on_appearance is not None:
            on_appearance(vm.effective_theme == ThemeMode.DARK)

    # 依赖取「解析后的明暗」而不是「用户选的模式」：跟随系统时，系统亮度变化
    # 也要让原生标题栏跟着换色。
    use_effect(push_theme, [color_theme, str(vm.effective_theme)])

    # —— 提示 —— #
    toast_serial = vm.toast.serial if vm.toast is not None else 0

    def show_toast() -> None:
        if vm.toast is None:
            return
        Message.info(vm.toast.message).show(page)

    use_effect(show_toast, [toast_serial])

    # —— 交互适配 —— #

    def run_async(
        handler: Callable[..., Coroutine[Any, Any, object]], *args: object
    ) -> None:
        """把协程方法排到事件循环执行（Flet 的同步事件回调入口）。"""
        page.run_task(handler, *args)

    def _remember_page_hooks() -> None:
        """页面级回调：全局快捷键。

        Esc 收起当前弹窗（桌面软件的常规预期；配色菜单由原生 PopupMenu 自己
        处理 Esc）；空格播放 / 暂停——但输入框有焦点时不抢空格。
        """

        def on_keyboard(e: KeyboardEvent) -> None:
            if e.key == "Escape":
                if sleep_dialog.current is not None:
                    close_sleep_dialog()
                return
            if e.key != " " or e.ctrl or e.alt or e.meta:
                return
            if search_focused.current:
                return
            run_async(vm.toggle_play)

        page.on_keyboard_event = on_keyboard

    use_effect(_remember_page_hooks, dependencies=[])

    # —— 睡眠定时器弹窗（视图自持的瞬时 UI 状态）—— #

    def close_sleep_dialog() -> None:
        if sleep_dialog.current is not None:
            try:
                page.pop_dialog()
            except Exception:
                pass
            sleep_dialog.current = None

    def start_sleep_timer(total: int) -> None:
        vm.start_sleep_timer(float(total))
        close_sleep_dialog()

    def cancel_sleep_timer() -> None:
        vm.cancel_sleep_timer()
        close_sleep_dialog()

    def open_sleep_dialog() -> None:
        if sleep_dialog.current is not None:
            return
        dialog = build_sleep_dialog(
            vm.sleep_remaining,
            start_sleep_timer,
            cancel_sleep_timer,
            close_sleep_dialog,
        )
        sleep_dialog.current = dialog
        page.show_dialog(dialog)

    # —— 提示文案 —— #
    track = vm.display_track

    def on_search_focus() -> None:
        search_focused.current = True

    def on_search_blur() -> None:
        search_focused.current = False

    toolbar = Container(
        content=Row(
            controls=[
                Row(
                    controls=[
                        Container(
                            content=Icon(
                                Icons.LIBRARY_MUSIC,
                                color=Colors.ON_PRIMARY,
                                size=20,
                            ),
                            width=36,
                            height=36,
                            alignment=Alignment.CENTER,
                            bgcolor=Colors.PRIMARY,
                            border_radius=10,
                        ),
                        Text(
                            "CS 音乐播放器",
                            size=16,
                            weight=FontWeight.W_700,
                            color=t.TEXT,
                        ),
                    ],
                    spacing=SPACE["3"],
                    vertical_alignment=CrossAxisAlignment.CENTER,
                ),
                Container(expand=True),
                SleepTimerButton(vm.sleep_remaining, open_sleep_dialog),
                DesktopLyricButton(
                    vm.desktop_enabled,
                    vm.desktop_locked,
                    vm.desktop_font,
                    vm.toggle_desktop_lyric,
                    vm.toggle_desktop_lock,
                    vm.step_desktop_font,
                    vm.reset_desktop_font,
                    vm.close_desktop_lyric,
                ),
                ThemeMenuButton(
                    color_theme,
                    theme_mode,
                    vm.set_color_theme,
                    vm.set_theme_mode,
                ),
                build_history_menu(
                    vm.recent_folders,
                    vm.pinned_folders,
                    lambda folder: run_async(vm.open_recent_folder, folder),
                    lambda folder: run_async(vm.toggle_pin_folder, folder),
                    lambda: run_async(vm.clear_recent_history),
                ),
                Button(
                    "导入音乐",
                    icon=Icons.FOLDER_OPEN,
                    style_type=StyleType.PRIMARY,
                    on_click=lambda e: run_async(vm.import_music_folder),
                ),
            ],
            spacing=SPACE["2"],
            vertical_alignment=CrossAxisAlignment.CENTER,
        ),
        bgcolor=t.PANEL,
        border=Border(bottom=BorderSide(1, t.LINE)),
        padding=Padding.symmetric(
            horizontal=SPACE["4"], vertical=TOOLBAR_PAD_Y
        ),
    )

    return Container(
        expand=True,
        bgcolor=t.CANVAS,
        content=Column(
            controls=[
                toolbar,
                Row(
                    controls=[
                        Sidebar(
                            vm.filtered_tracks,
                            vm.filtered_selected,
                            vm.playing_track,
                            vm.search,
                            vm.show_favorites,
                            vm.playlist_count,
                            vm.set_search,
                            vm.set_favorites_only,
                            vm.select,
                            vm.play,
                            vm.toggle_favorite,
                            vm.is_playing,
                            on_search_focus,
                            on_search_blur,
                        ),
                        MainStage(
                            track,
                            vm.is_playing,
                            vm.lyrics,
                            vm.active_lyric_index,
                            vm.has_lyrics,
                            vm.lyric_offset,
                            vm.lyric_font,
                            vm.adjust_lyric_offset,
                            vm.adjust_lyric_font,
                        ),
                    ],
                    expand=True,
                    spacing=0,
                ),
                PlayerBar(
                    track,
                    vm.is_playing,
                    vm.position,
                    vm.duration,
                    vm.volume,
                    vm.speed,
                    str(vm.mode),
                    dragging,
                    lambda e: run_async(vm.toggle_play),
                    lambda e: run_async(vm.previous_track),
                    lambda e: run_async(vm.next_track),
                    lambda e: vm.cycle_mode(),
                    vm.seek,
                    vm.set_volume,
                    vm.set_speed,
                ),
            ],
            spacing=0,
            expand=True,
        ),
    )


# ── 工具栏：历史文件夹菜单 ── #

#: 菜单宽度：够放下「盘符 + 两级目录名」，再宽就变成一堵墙。
HISTORY_MENU_WIDTH = 300


def build_history_menu(
    recent: list[str],
    pinned: set[str],
    on_open: Callable[[str], None],
    on_toggle_pin: Callable[[str], None],
    on_clear: Callable[[], None],
) -> PopupMenuButton:
    """历史文件夹下拉菜单：固定组在前、最近组在后，每条都能就地固定 / 取消。

    两级分组解决一个具体问题：常用的三个文件夹会随使用不断往下沉，固定之后就
    永远在手边。
    """
    pinned_list = [folder for folder in recent if folder in pinned] + [
        folder for folder in sorted(pinned) if folder not in recent
    ]
    recent_list = [folder for folder in recent if folder not in pinned]

    items: list[PopupMenuItem] = []
    if pinned_list:
        items.append(_menu_header("固定文件夹"))
        items.extend(
            _folder_item(folder, True, on_open, on_toggle_pin) for folder in pinned_list
        )
        if recent_list:
            items.append(_menu_divider())
    if recent_list:
        items.append(_menu_header("最近打开"))
        items.extend(
            _folder_item(folder, False, on_open, on_toggle_pin)
            for folder in recent_list
        )
    if not pinned_list and not recent_list:
        items.append(
            PopupMenuItem(
                content=Text("暂无历史文件夹", size=12, color=t.TEXT_SOFT),
                on_click=lambda e: None,
            )
        )
    elif recent_list:
        items.append(_menu_divider())
        items.append(
            PopupMenuItem(
                content=Row(
                    controls=[
                        Icon(Icons.DELETE_OUTLINE, size=15, color=t.TEXT_SOFT),
                        Text("清空历史", size=12, color=t.TEXT_SOFT),
                    ],
                    spacing=SPACE["2"],
                ),
                on_click=lambda e: on_clear(),
            )
        )

    return PopupMenuButton(
        icon=Icons.HISTORY,
        icon_color=t.TEXT_SOFT,
        icon_size=22,
        tooltip="历史文件夹",
        style=ButtonStyle(padding=Padding.all(8)),
        menu_position=PopupMenuPosition.UNDER,
        size_constraints=BoxConstraints(
            min_width=HISTORY_MENU_WIDTH, max_width=HISTORY_MENU_WIDTH
        ),
        items=items,
    )


def _menu_header(text: str) -> PopupMenuItem:
    """分组标题：不可点，只用来「分段」。"""
    return PopupMenuItem(
        content=Text(
            text,
            size=11,
            weight=FontWeight.W_600,
            color=t.TEXT_SOFT,
        ),
        height=32,
    )


def _menu_divider() -> PopupMenuItem:
    return PopupMenuItem(content=Divider(height=1, color=t.LINE), height=1)


def _folder_item(
    folder: str,
    pinned: bool,
    on_open: Callable[[str], None],
    on_toggle_pin: Callable[[str], None],
) -> PopupMenuItem:
    """一条历史记录：左边图标表示「已固定 / 普通」，右边图钉就地固定。"""
    path = Path(folder)
    name = path.name or folder
    return PopupMenuItem(
        tooltip=folder,
        content=Row(
            controls=[
                Icon(
                    Icons.PUSH_PIN if pinned else Icons.FOLDER_OPEN,
                    size=15,
                    color=t.ACCENT if pinned else t.TEXT_SOFT,
                ),
                Text(
                    name,
                    size=12,
                    color=t.TEXT,
                    max_lines=1,
                    overflow=TextOverflow.ELLIPSIS,
                    expand=True,
                ),
                IconButton(
                    icon=Icons.PUSH_PIN_OUTLINED if not pinned else Icons.PUSH_PIN,
                    icon_size=14,
                    icon_color=t.ACCENT if pinned else t.TEXT_SOFT,
                    tooltip="取消固定" if pinned else "固定文件夹",
                    on_click=lambda e, f=folder: on_toggle_pin(f),
                    padding=Padding.all(2),
                ),
            ],
            spacing=SPACE["2"],
            vertical_alignment=CrossAxisAlignment.CENTER,
        ),
        on_click=lambda e, f=folder: on_open(f),
    )
