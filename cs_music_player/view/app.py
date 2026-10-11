"""视图层根组件：把视图模型的状态声明式地渲染成界面。

本模块是**纯视图**：不导入 service / infra，不做业务流程，只做两件事——

1. 读 :class:`~cs_music_player.viewmodel.app.AppViewModel` 的状态，构造控件树；
2. 把用户操作转成视图模型的方法调用。

状态变化由视图模型广播，本组件订阅后重渲染，因此「UI = f(状态)」。
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from pathlib import Path

import flet as ft

from typing import Any

from ..viewmodel import AppViewModel
from .components import (
    DesktopLyricButton,
    MainStage,
    PlayerBar,
    Sidebar,
    SleepTimerButton,
    build_sleep_dialog,
)
from .theme import THEME_ICONS, THEME_LABELS, palette

__all__ = ["PlayerApp"]


def apply_theme_mode(page: ft.Page, mode: str) -> None:
    """把主题模式应用到全局调色板与 Flet Material 主题。

    必须在**构造控件之前**调用——组件在渲染时读 ``palette.*``，先换表后
    渲染，同一次渲染里所有组件拿到的才是同一套颜色。
    """
    palette.set_mode(mode)
    page.theme_mode = ft.ThemeMode.DARK if mode == "dark" else ft.ThemeMode.LIGHT
    page.bgcolor = palette.BG


@ft.component
def PlayerApp(page: ft.Page, vm: AppViewModel) -> ft.Control:
    """应用主界面。"""
    # 视图模型是不可变数据源；用一个自增版本号驱动整棵树重渲染。
    revision, set_revision = ft.use_state(0)
    invalidate = ft.use_ref(lambda: None)
    dragging = ft.use_ref(False)
    search_focused = ft.use_ref(False)
    sleep_dialog = ft.use_ref(None)

    def bump_revision() -> None:
        set_revision(lambda value: value + 1)

    invalidate.current = bump_revision

    def on_state_changed() -> None:
        """视图模型变了：重渲染整棵树。"""
        invalidate.current()

    ft.use_effect(lambda: vm.subscribe(on_state_changed), [vm])
    ft.use_effect(lambda: _remember_page_hooks(), dependencies=[])

    # —— 主题：先换调色板，再渲染 —— #
    effective_theme = str(vm.effective_theme)
    apply_theme_mode(page, effective_theme)

    def push_page_theme() -> None:
        """主题是页面级属性：渲染完把补丁推给客户端。

        组件模式下属性赋值不会自动下发，必须显式 ``page.update()``；
        调色板已经在渲染前切好，所以这里只补页面自身的属性。
        """
        apply_theme_mode(page, str(vm.effective_theme))
        page.update()

    ft.use_effect(push_page_theme, [effective_theme])

    # —— 提示 —— #
    toast_serial = vm.toast.serial if vm.toast is not None else 0

    def show_toast() -> None:
        if vm.toast is None:
            return
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(vm.toast.message),
                behavior=ft.SnackBarBehavior.FLOATING,
                margin=ft.Margin.only(left=16, right=16, bottom=16),
                duration=ft.Duration(milliseconds=2200),
                bgcolor=palette.SURFACE,
            )
        )

    ft.use_effect(show_toast, [toast_serial])

    # —— 交互适配：视图只负责把事件转成视图模型调用 —— #
    def run_async(
        handler: Callable[..., Coroutine[Any, Any, object]], *args: object
    ) -> None:
        """把协程方法排到事件循环执行（Flet 的同步事件回调入口）。"""
        page.run_task(handler, *args)

    def _remember_page_hooks() -> None:
        """页面级回调：平台亮度变化时通知视图模型。"""

        def on_brightness(e: ft.ControlEvent) -> None:
            vm.set_system_brightness(str(page.platform_brightness))

        def on_keyboard(e: ft.KeyboardEvent) -> None:
            if e.key != " " or e.ctrl or e.alt or e.meta:
                return
            if search_focused.current:
                return
            run_async(vm.toggle_play)

        page.on_platform_brightness_change = on_brightness
        page.on_keyboard_event = on_keyboard

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

    # —— 工具栏：历史文件夹菜单 —— #

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
                        color=palette.ACCENT if pinned else palette.PRIMARY_DARK,
                    ),
                    ft.Text(
                        name,
                        size=12,
                        color=palette.TEXT_MAIN,
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
                        icon_color=palette.ACCENT if pinned else palette.TEXT_MUTED,
                        tooltip="取消固定" if pinned else "固定文件夹",
                        on_click=lambda e, f=folder: run_async(vm.toggle_pin_folder, f),
                        padding=ft.Padding.all(2),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e, f=folder: run_async(vm.open_recent_folder, f),
        )

    def build_section_header(text: str) -> ft.PopupMenuItem:
        return ft.PopupMenuItem(
            content=ft.Text(
                text,
                size=11,
                weight=ft.FontWeight.W_600,
                color=palette.TEXT_MUTED,
            ),
            height=32,
        )

    recent_items: list[ft.PopupMenuItem] = []
    pinned_set = set(vm.pinned_folders)
    pinned_list = [f for f in vm.recent_folders if f in pinned_set] + [
        f for f in sorted(pinned_set) if f not in vm.recent_folders
    ]
    recent_list = [f for f in vm.recent_folders if f not in pinned_set]
    if pinned_list:
        recent_items.append(build_section_header("固定文件夹"))
        recent_items.extend(build_folder_item(f, True) for f in pinned_list)
        if recent_list:
            recent_items.append(
                ft.PopupMenuItem(
                    content=ft.Divider(height=1, color=palette.BORDER),
                    height=1,
                )
            )
    if recent_list:
        recent_items.append(build_section_header("最近打开"))
        recent_items.extend(build_folder_item(f, False) for f in recent_list)
    if not pinned_list and not recent_list:
        recent_items.append(
            ft.PopupMenuItem(
                content=ft.Text("暂无历史文件夹", size=12, color=palette.TEXT_MUTED),
                on_click=lambda e: None,
            )
        )
    elif recent_list:
        recent_items.append(
            ft.PopupMenuItem(
                content=ft.Divider(height=1, color=palette.BORDER),
                height=1,
            )
        )
        recent_items.append(
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.DELETE_OUTLINE, size=15, color=palette.TEXT_MUTED
                        ),
                        ft.Text("清空历史", size=12, color=palette.TEXT_DIM),
                    ],
                    spacing=8,
                ),
                on_click=lambda e: run_async(vm.clear_recent_history),
            )
        )

    menu_width = 300
    theme = vm.theme_mode
    track = vm.display_track

    toolbar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.LIBRARY_MUSIC, color=palette.SURFACE, size=20
                            ),
                            width=36,
                            height=36,
                            alignment=ft.Alignment.CENTER,
                            bgcolor=palette.PRIMARY,
                            border_radius=10,
                        ),
                        ft.Text(
                            "CS 音乐播放器",
                            size=16,
                            weight=ft.FontWeight.W_700,
                            color=palette.TEXT_MAIN,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(expand=True),
                ft.Text(
                    "正在播放" if vm.is_playing and track else "",
                    size=12,
                    color=palette.TEXT_DIM,
                    italic=True,
                ),
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
                ft.IconButton(
                    icon=THEME_ICONS[theme],
                    icon_color=palette.TEXT_DIM,
                    icon_size=20,
                    tooltip=f"主题：{THEME_LABELS[theme]}（点击切换）",
                    on_click=lambda e: vm.cycle_theme(),
                    style=ft.ButtonStyle(
                        padding=ft.Padding.all(8),
                        overlay_color=ft.Colors.with_opacity(0.08, palette.PRIMARY),
                    ),
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.HISTORY,
                    icon_color=palette.PRIMARY_DARK,
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
                    on_click=lambda e: run_async(vm.import_music_folder),
                    style=ft.ButtonStyle(
                        bgcolor={
                            ft.ControlState.DEFAULT: palette.PRIMARY,
                            ft.ControlState.HOVERED: palette.PRIMARY_DARK,
                        },
                        color=ft.Colors.WHITE,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=palette.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, palette.BORDER)),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
    )

    def on_search_focus() -> None:
        search_focused.current = True

    def on_search_blur() -> None:
        search_focused.current = False

    return ft.Container(
        expand=True,
        bgcolor=palette.BG,
        content=ft.Column(
            [
                toolbar,
                ft.Row(
                    [
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

