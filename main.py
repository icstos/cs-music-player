"""
本地音乐播放器 —— 基于 Flet 0.85 现代响应式 API 重构。

设计要点
--------
* 数据层：`Track` 用 `@ft.observable`，字段变更可被组件自动感知。
* 逻辑层：`Player` 只负责封装 `flet_audio.Audio` 与索引/模式计算，
  通过回调把状态变化推回 UI，做到逻辑与视图解耦。
* 视图层：顶层 `PlayerApp` 用 `use_state` 集中持有 UI 状态，
  各子组件以 `@ft.component` 纯函数实现、props 驱动、自动重渲染。
* 入口：`ft.run(main)`（替代旧 `ft.app`）。

运行：`python main.py`，启动后点「打开文件夹」导入音乐即可。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import flet as ft
import pygame

# ──────────────────────────────────────────────────────────────────────────
# ① 常量与配置
# ──────────────────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")

# 播放模式（顺序 → 单曲循环 → 随机，循环切换）
MODE_SEQUENCE = "顺序播放"
MODE_LOOP_ONE = "单曲循环"
MODE_SHUFFLE = "随机播放"
_MODE_ORDER = (MODE_SEQUENCE, MODE_LOOP_ONE, MODE_SHUFFLE)
_MODE_ICON = {
    MODE_SEQUENCE: ft.Icons.REPEAT,
    MODE_LOOP_ONE: ft.Icons.REPEAT_ONE,
    MODE_SHUFFLE: ft.Icons.SHUFFLE,
}

# 配色（QQ / 网易云现代深色风，紫色品牌色点缀）
BRAND = ft.Colors.DEEP_PURPLE
BRAND_400 = ft.Colors.DEEP_PURPLE_400
SURFACE = "#1e1b2e"            # 卡片底色
SURFACE_SOFT = "#27233a"       # 次级卡片底色
TEXT_MAIN = ft.Colors.WHITE
TEXT_DIM = ft.Colors.GREY_400


# ──────────────────────────────────────────────────────────────────────────
# 异步文件夹选择器（FilePicker 在 flet 0.85.x Flutter 后端不支持，
# 改用 stdlib tkinter + run_in_executor 不阻塞 UI）
# ──────────────────────────────────────────────────────────────────────────


async def _pick_folder_async(title: str = "选择音乐文件夹") -> str | None:
    """在后台线程弹出系统原生文件夹选择对话框。"""
    import tkinter as tk
    from tkinter import filedialog

    def _run():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return filedialog.askdirectory(title=title)
        finally:
            root.destroy()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


# ──────────────────────────────────────────────────────────────────────────
# ② 数据模型
# ──────────────────────────────────────────────────────────────────────────


@ft.observable
@dataclass
class Track:
    """一首音乐。observable 使得字段变更可被组件自动感知。"""

    path: Path
    title: str = ""
    duration: float = 0.0          # 秒；加载后由播放器回调回填

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.path.stem


# ──────────────────────────────────────────────────────────────────────────
# ③ 播放器核心（纯逻辑）
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class PlayerCallbacks:
    """UI 层注入的回调，把播放器内部状态变化推回视图层。"""

    on_position: Callable[[float], None]
    on_duration: Callable[[float], None]
    on_play_state: Callable[[bool], None]
    on_track_change: Callable[[int], None]   # 切到新曲目（含自动连播）


class Player:
    """封装 pygame.mixer.music，对外暴露高层播放语义。

    通过 asyncio 轮询当前位置并通过回调推回 UI 层。
    使用 mutagen 读取音频文件时长（不加载整个文件）。
    """

    # 每轮询一次检查的 pygame 事件（用于曲目播放结束通知）
    _END_EVENT = pygame.USEREVENT + 1

    def __init__(self, callbacks: PlayerCallbacks) -> None:
        self._cb = callbacks
        self.tracks: list[Track] = []
        self.current: int = -1
        self.mode: str = MODE_SEQUENCE
        self._playing: bool = False
        self._volume: float = 0.7
        self._poll_stop: bool = False

        # 初始化 pygame mixer（采样率 / 缓冲区）
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        pygame.mixer.music.set_volume(self._volume)
        pygame.mixer.music.set_endevent(self._END_EVENT)

        # 启动位置轮询任务
        self._poll_task: asyncio.Task = asyncio.ensure_future(self._poll_loop())

    async def _poll_loop(self) -> None:
        """250ms 轮询一次：推送位置、检测曲目结束。"""
        while not self._poll_stop:
            if self._playing:
                pos_ms = pygame.mixer.music.get_pos()
                if pos_ms >= 0:
                    self._cb.on_position(pos_ms / 1000.0)
            # 处理 pygame 事件（曲目结束通知）
            for event in pygame.event.get():
                if event.type == self._END_EVENT:
                    self._playing = False
                    self._cb.on_play_state(False)
                    await self.next(auto=True)
            await asyncio.sleep(0.25)

    def _load_track(self, filepath: Path) -> None:
        """加载音频文件；从 mutagen 获取时长。"""
        self._playing = False
        try:
            from mutagen import File

            audio = File(str(filepath))
            if audio is not None and hasattr(audio, "info"):
                self._cb.on_duration(audio.info.length)
            else:
                self._cb.on_duration(0.0)
        except Exception:
            self._cb.on_duration(0.0)
        pygame.mixer.music.load(str(filepath))

    # —— 曲目管理 —— #
    def set_tracks(self, tracks: list[Track]) -> None:
        self.tracks = tracks
        self.current = -1 if not tracks else 0

    def _index_after_end(self) -> int | None:
        if not self.tracks:
            return None
        if self.mode == MODE_LOOP_ONE:
            return self.current
        if self.mode == MODE_SHUFFLE:
            import random

            if len(self.tracks) == 1:
                return self.current
            idx = random.randrange(len(self.tracks) - 1)
            return idx if idx < self.current else idx + 1
        nxt = self.current + 1
        return nxt if nxt < len(self.tracks) else None

    # —— 播放控制 —— #
    async def play_at(self, index: int) -> None:
        if not (0 <= index < len(self.tracks)):
            return
        self.current = index
        track = self.tracks[index]
        self._load_track(track.path)
        pygame.mixer.music.play()
        self._playing = True
        self._cb.on_play_state(True)
        self._cb.on_track_change(index)

    async def toggle(self) -> None:
        if self.current < 0:
            if self.tracks:
                await self.play_at(0)
            return
        if self._playing:
            pygame.mixer.music.pause()
            self._playing = False
            self._cb.on_play_state(False)
        else:
            pygame.mixer.music.unpause()
            self._playing = True
            self._cb.on_play_state(True)

    async def next(self, auto: bool = False) -> None:
        if not self.tracks:
            return
        if auto:
            target = self._index_after_end()
            if target is None:
                self._cb.on_play_state(False)
                return
        else:
            target = (self.current + 1) % len(self.tracks) if self.current >= 0 else 0
        await self.play_at(target)

    async def prev(self) -> None:
        if not self.tracks:
            return
        if self.current < 0:
            await self.play_at(0)
            return
        target = (self.current - 1) % len(self.tracks)
        await self.play_at(target)

    async def seek(self, seconds: float) -> None:
        try:
            pygame.mixer.music.set_pos(seconds)
        except pygame.error:
            pass  # 某些格式（如 MOD）不支持 seek

    def set_volume(self, value01: float) -> None:
        self._volume = max(0.0, min(1.0, value01))
        pygame.mixer.music.set_volume(self._volume)

    def cycle_mode(self) -> str:
        self.mode = _MODE_ORDER[(_MODE_ORDER.index(self.mode) + 1) % len(_MODE_ORDER)]
        return self.mode

    def shutdown(self) -> None:
        """停止轮询并释放资源。"""
        self._poll_stop = True
        pygame.mixer.music.stop()
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()


# ──────────────────────────────────────────────────────────────────────────
# ④ UI 组件（@ft.component，纯函数 + props 驱动）
# ──────────────────────────────────────────────────────────────────────────


def _fmt(seconds: float) -> str:
    """秒数 → `m:ss`。"""
    if seconds <= 0 or seconds != seconds:  # nan 判断
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _card(controls: list, *, soft: bool = False, **kw) -> ft.Container:
    """统一的圆角卡片容器。"""
    return ft.Container(
        content=ft.Column(controls, spacing=12) if not kw.pop("row", False)
        else ft.Row(controls, **{k: v for k, v in kw.items()}),
        bgcolor=SURFACE_SOFT if soft else SURFACE,
        border_radius=16,
        padding=20,
    )


@ft.component
def PlaylistItem(
    track: Track,
    index: int,
    is_current: bool,
    on_click: Callable[[int], None],
) -> ft.Control:
    """播放列表的单行。"""
    async def _on_click(e: ft.ControlEvent) -> None:
        await on_click(index)

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.GRAPHIC_EQ if is_current else ft.Icons.MUSIC_NOTE,
                    color=BRAND_400 if is_current else TEXT_DIM,
                    size=20,
                ),
                ft.Column(
                    [
                        ft.Text(
                            track.title,
                            size=14,
                            weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                            color=TEXT_MAIN if is_current else TEXT_DIM,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            str(track.path),
                            size=11,
                            color=ft.Colors.GREY_600,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=ft.Colors.with_opacity(0.18, BRAND) if is_current else ft.Colors.TRANSPARENT,
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        on_click=_on_click,
        ink=True,
    )


@ft.component
def Playlist(
    tracks: list[Track],
    current: int,
    on_select: Callable[[int], None],
) -> ft.Control:
    """播放列表区域。"""
    if not tracks:
        return _card([
            ft.Row(
                [ft.Icon(ft.Icons.QUEUE_MUSIC, color=TEXT_DIM), ft.Text("播放列表为空，点击右上角导入音乐", color=TEXT_DIM)],
                alignment=ft.MainAxisAlignment.CENTER,
            )
        ])

    items = [
        PlaylistItem(t, i, i == current, on_select)
        for i, t in enumerate(tracks)
    ]
    list_view = ft.ListView(
        controls=items,
        spacing=4,
        padding=4,
        expand=True,
        height=320,
    )
    header = ft.Row(
        [
            ft.Icon(ft.Icons.QUEUE_MUSIC, color=BRAND_400),
            ft.Text(f"播放列表（{len(tracks)}）", size=18, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    return _card([header, list_view])


@ft.component
def ProgressBar(
    position: float,
    duration: float,
    dragging: ft.MutableRef[bool],
    on_seek: Callable[[float], None],
) -> ft.Control:
    """进度条：拖动结束后回调 on_seek(秒)。"""
    # 当前比例：拖动期间用本地状态，否则用真实进度
    local_value, set_local = ft.use_state(0.0)

    def on_change(e: ft.ControlEvent) -> None:
        set_local(float(e.control.value))
        dragging.current = True

    async def on_release(e: ft.ControlEvent) -> None:
        if duration > 0:
            await on_seek(float(e.control.value) * duration)
        dragging.current = False

    shown = local_value if dragging.current else (position / duration if duration > 0 else 0.0)

    return ft.Column(
        [
            ft.Slider(
                min=0,
                max=1,
                value=shown,
                active_color=BRAND_400,
                thumb_color=BRAND,
                on_change=on_change,
                on_change_end=on_release,
                expand=True,
            ),
            ft.Row(
                [
                    ft.Text(_fmt(position), size=12, color=TEXT_DIM),
                    ft.Container(expand=True),
                    ft.Text(_fmt(duration), size=12, color=TEXT_DIM),
                ]
            ),
        ],
        spacing=2,
    )


@ft.component
def VolumeControl(
    volume: float,
    on_change: Callable[[float], None],
) -> ft.Control:
    """音量控制，图标随音量变化。"""
    icon = (
        ft.Icons.VOLUME_MUTE if volume == 0
        else ft.Icons.VOLUME_DOWN if volume < 0.5
        else ft.Icons.VOLUME_UP
    )
    return ft.Row(
        [
            ft.Icon(icon, color=BRAND_400, size=22),
            ft.Slider(
                min=0,
                max=1,
                value=volume,
                active_color=BRAND_400,
                thumb_color=BRAND,
                on_change=lambda e: on_change(float(e.control.value)),
                width=130,
            ),
        ],
        spacing=8,
    )


@ft.component
def PlayControls(
    is_playing: bool,
    mode: str,
    has_tracks: bool,
    on_toggle: Callable[[ft.ControlEvent], None],
    on_prev: Callable[[ft.ControlEvent], None],
    on_next: Callable[[ft.ControlEvent], None],
    on_mode: Callable[[ft.ControlEvent], None],
) -> ft.Control:
    """底部播放控制条。"""
    return ft.Row(
        [
            ft.IconButton(
                icon=_MODE_ICON[mode],
                icon_color=BRAND_400,
                tooltip=mode,
                on_click=on_mode,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_PREVIOUS_ROUNDED,
                icon_color=TEXT_MAIN,
                icon_size=36,
                tooltip="上一曲",
                on_click=on_prev,
            ),
            ft.IconButton(
                icon=ft.Icons.PAUSE_CIRCLE_FILLED_ROUNDED if is_playing
                else ft.Icons.PLAY_CIRCLE_FILL_ROUNDED,
                icon_color=BRAND_400,
                icon_size=56,
                tooltip="播放/暂停",
                on_click=on_toggle,
            ),
            ft.IconButton(
                icon=ft.Icons.SKIP_NEXT_ROUNDED,
                icon_color=TEXT_MAIN,
                icon_size=36,
                tooltip="下一曲",
                on_click=on_next,
            ),
            ft.Container(
                content=ft.Text(
                    "♪" if has_tracks else "",
                    size=18,
                    color=ft.Colors.with_opacity(0.4, BRAND_400),
                ),
                width=44,
                alignment=ft.Alignment.CENTER,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=18,
    )


@ft.component
def NowPlaying(track: Track | None, is_playing: bool) -> ft.Control:
    """正在播放信息卡：封面占位 + 标题。"""
    if track is None:
        title_text = "未选择歌曲"
        sub_text = "请导入音乐文件夹"
    else:
        title_text = track.title
        sub_text = track.path.parent.name  # 用所在文件夹名作"专辑"占位

    return ft.Row(
        [
            ft.Container(
                content=ft.Icon(
                    ft.Icons.GRAPHIC_EQ if is_playing else ft.Icons.ALBUM,
                    size=64,
                    color=BRAND_400,
                ),
                width=96,
                height=96,
                alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.with_opacity(0.15, BRAND),
                border_radius=16,
            ),
            ft.Column(
                [
                    ft.Text(
                        title_text,
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_MAIN,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(sub_text, size=13, color=TEXT_DIM),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
        ],
        alignment=ft.MainAxisAlignment.START,
        spacing=18,
    )


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 顶层应用组件
# ──────────────────────────────────────────────────────────────────────────


@ft.component
def PlayerApp(page: ft.Page) -> ft.Control:
    """顶层组件：集中持有 UI 状态，组装整体布局。"""

    # —— 集中式 UI 状态（变更即触发依赖组件重渲染）—— #
    tracks, set_tracks = ft.use_state(list[Track]())
    current, set_current = ft.use_state(-1)
    is_playing, set_is_playing = ft.use_state(False)
    position, set_position = ft.use_state(0.0)
    duration, set_duration = ft.use_state(0.0)
    volume, set_volume = ft.use_state(0.7)
    mode, set_mode = ft.use_state(MODE_SEQUENCE)

    dragging = ft.use_ref(False)        # 进度条拖动标记（不触发渲染）
    player_ref = ft.use_ref(None)       # Player 实例（不触发渲染）

    # —— 挂载时初始化播放器 —— #
    def setup_player() -> None:
        player_ref.current = Player(
            PlayerCallbacks(
                on_position=set_position,
                on_duration=set_duration,
                on_play_state=set_is_playing,
                on_track_change=set_current,
            ),
        )

    ft.use_effect(setup_player, dependencies=[])

    # —— 事件处理函数（直接定义 async，Flet 会 await 它们）—— #
    async def on_import_click(e: ft.ControlEvent) -> None:
        directory = await _pick_folder_async("选择音乐文件夹")
        if not directory:
            return
        files = [
            Track(path=f)
            for f in sorted(Path(directory).iterdir())
            if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
        ]
        if not files:
            return
        player = player_ref.current
        player.set_tracks(files)
        set_tracks(files)
        set_current(0)
        set_position(0.0)
        set_duration(0.0)

    async def on_toggle_click(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.toggle()

    async def on_next_click(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.next()

    async def on_prev_click(e: ft.ControlEvent) -> None:
        if player_ref.current:
            await player_ref.current.prev()

    def on_volume_change(v: float) -> None:
        set_volume(v)
        if player_ref.current:
            player_ref.current.set_volume(v)

    def on_mode_cycle(e: ft.ControlEvent) -> None:
        if player_ref.current:
            set_mode(player_ref.current.cycle_mode())

    async def on_select_track(index: int) -> None:
        if player_ref.current:
            await player_ref.current.play_at(index)

    async def on_seek(seconds: float) -> None:
        if player_ref.current:
            await player_ref.current.seek(seconds)
            set_position(seconds)

    # —— 布局 —— #
    track = tracks[current] if 0 <= current < len(tracks) else None

    header = ft.Row(
        [
            ft.Icon(ft.Icons.LIBRARY_MUSIC, color=BRAND_400, size=30),
            ft.Text("CS 音乐播放器", size=24, weight=ft.FontWeight.BOLD, color=TEXT_MAIN),
            ft.Container(expand=True),
            ft.Button(
                "打开文件夹",
                icon=ft.Icons.FOLDER_OPEN,
                on_click=on_import_click,
                style=ft.ButtonStyle(bgcolor=BRAND, color=TEXT_MAIN),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    return ft.Column(
        [
            header,
            _card([NowPlaying(track, is_playing)], soft=True),
            _card([
                ProgressBar(position, duration, dragging, on_seek),
                PlayControls(
                    is_playing, mode, bool(tracks),
                    on_toggle=on_toggle_click,
                    on_prev=on_prev_click,
                    on_next=on_next_click,
                    on_mode=on_mode_cycle,
                ),
                VolumeControl(volume, on_volume_change),
            ]),
            Playlist(tracks, current, on_select_track),
        ],
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# ⑥ 入口
# ──────────────────────────────────────────────────────────────────────────


def main(page: ft.Page) -> None:
    page.title = "CS 音乐播放器"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=BRAND)
    page.bgcolor = "#13111c"
    page.window.width = 1000
    page.window.height = 720
    page.window.min_width = 760
    page.window.min_height = 600
    page.padding = 24

    # page.render 设置组件渲染器并挂载组件树（page.add 不支持 @component）
    page.render(PlayerApp, page)


if __name__ == "__main__":
    ft.run(main)
