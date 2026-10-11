"""应用视图模型：持有全部 UI 状态，连接视图与服务。

设计要点：

- **纯 Python**：不导入 ``flet``，不持有任何 UI 控件，只暴露状态与动作，
  因此可以在无界面环境下被完整单测。
- **UI = f(状态)**：界面能画出来的一切都是本类的属性；派生量（当前曲目、
  过滤后的列表、正在高亮的歌词行……）都是只读 property，不重复存储。
- **单向数据流**：视图只调用这里的方法；这里的回调（播放器事件、悬浮窗
  事件、睡眠倒计时）改完状态后统一 :meth:`notify`，视图据此重渲染。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import (
    DESKTOP_LYRIC_FONT_DEFAULT,
    DESKTOP_LYRIC_FONT_STEP,
    LYRIC_FONT_DEFAULT,
    THEME_MODES,
    DesktopLyricConfig,
    LyricLine,
    PlayMode,
    ThemeMode,
    Track,
    track_key,
)
from ..models import clamp_lyric_font
from ..service.library import apply_favorites, filter_tracks
from ..service.lyrics import current_line_index
from ..service.playback import PlaybackObserver
from ..service.sleep import SleepTimerService
from .observable import ObservableModel
from .ports import (
    DesktopLyricOps,
    FolderHistoryOps,
    LibraryOps,
    LyricsOps,
    PlaybackOps,
    SettingsOps,
)

__all__ = ["AppViewModel", "Toast"]


@dataclass(frozen=True)
class Toast:
    """一条一次性提示（视图据此弹 SnackBar）。"""

    message: str
    serial: int


class AppViewModel(ObservableModel):
    """整个应用的状态与动作。

    Args:
        playback_factory: 用本视图模型（作为播放观察者）构造播放服务。
        library: 音乐库能力（目录选择、扫描、曲目、收藏）。
        folders: 文件夹历史能力（最近打开、固定）。
        lyrics: 歌词能力。
        settings: 设置能力。
        desktop_lyric: 桌面歌词能力。

    除 ``playback_factory`` 外，其余参数都只要求满足 :mod:`viewmodel.ports`
    里定义的 ``Protocol``——具体实现由组装根注入，本层不认识任何服务类。
        on_close_requested: 睡眠定时器到点后请求关闭软件（组装根注入）。
    """

    def __init__(
        self,
        *,
        playback_factory: Callable[[PlaybackObserver], PlaybackOps],
        library: LibraryOps,
        folders: FolderHistoryOps,
        lyrics: LyricsOps,
        settings: SettingsOps,
        desktop_lyric: DesktopLyricOps,
        on_close_requested: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._library = library
        self._folders = folders
        self._lyrics = lyrics
        self._settings = settings
        self._desktop = desktop_lyric
        self._on_close_requested = on_close_requested
        self._favorites: set[str] = set()
        self._tasks: set[asyncio.Task[Any]] = set()

        # —— UI 状态（界面完全由这些字段派生）—— #
        self.theme_mode: ThemeMode = ThemeMode.SYSTEM
        self.system_brightness: str = "light"
        self.tracks: list[Track] = []
        self.selected: int = -1
        self.current: int = -1
        self.is_playing: bool = False
        self.position: float = 0.0
        self.duration: float = 0.0
        self.volume: float = 0.7
        self.speed: float = 1.0
        self.mode: PlayMode = PlayMode.SEQUENCE
        self.sleep_remaining: float = 0.0
        self.lyrics: list[LyricLine] = []
        self.lyric_offset: float = 0.0
        self.lyric_font: float = LYRIC_FONT_DEFAULT
        self.desktop_enabled: bool = False
        self.desktop_locked: bool = False
        self.desktop_font: float = DESKTOP_LYRIC_FONT_DEFAULT
        self.search: str = ""
        self.show_favorites: bool = False
        self.recent_folders: list[str] = []
        self.pinned_folders: set[str] = set()
        self.toast: Toast | None = None

        self._toast_serial = 0
        self._playback = playback_factory(self)
        self._desktop.subscribe(self)
        self._sleep = SleepTimerService(
            on_tick=self._on_sleep_tick,
            on_elapsed=self._on_sleep_elapsed,
        )

    # ────────────────────────────────────────────────
    #  派生状态（只读；视图直接用，不重复存储）
    # ────────────────────────────────────────────────

    @property
    def playing_track(self) -> Track | None:
        """正在播放的曲目（未播放时为 ``None``）。"""
        if 0 <= self.current < len(self.tracks):
            return self.tracks[self.current]
        return None

    @property
    def display_track(self) -> Track | None:
        """界面当前展示的曲目：优先正在播放，其次列表中选中的那首。"""
        index = self.current if self.current >= 0 else self.selected
        if 0 <= index < len(self.tracks):
            return self.tracks[index]
        return None

    @property
    def filtered_tracks(self) -> list[Track]:
        """按搜索词与「仅收藏」筛选后的曲目列表。"""
        return filter_tracks(
            self.tracks, self.search, favorites_only=self.show_favorites
        )

    @property
    def filtered_selected(self) -> int:
        """选中项在筛选结果里的下标（不在结果里时为 ``-1``）。"""
        if not (0 <= self.selected < len(self.tracks)):
            return -1
        target = self.tracks[self.selected]
        for index, track in enumerate(self.filtered_tracks):
            if track is target:
                return index
        return -1

    @property
    def playlist_count(self) -> int:
        """音乐库总曲目数。"""
        return len(self.tracks)

    @property
    def has_lyrics(self) -> bool:
        """当前展示的曲目是否有歌词文件。"""
        track = self.display_track
        return bool(track and track.lyrics_path)

    @property
    def active_lyric_index(self) -> int:
        """当前应高亮的歌词行下标（无歌词为 ``-1``）。"""
        return current_line_index(self.lyrics, self.position, self.lyric_offset)

    @property
    def desktop_lyric_lines(self) -> list[str]:
        """推给桌面歌词悬浮窗的文本行。"""
        return [line.text for line in self.lyrics]

    @property
    def effective_theme(self) -> ThemeMode:
        """把「跟随系统」解析成实际的亮 / 暗主题。"""
        if self.theme_mode == ThemeMode.SYSTEM:
            return (
                ThemeMode.DARK
                if self.system_brightness == "dark"
                else ThemeMode.LIGHT
            )
        return self.theme_mode

    # ────────────────────────────────────────────────
    #  生命周期
    # ────────────────────────────────────────────────

    async def initialize(self, startup_path: Path | None = None) -> None:
        """启动时恢复持久化设置，并按需加载启动路径。"""
        self.recent_folders = await self._folders.recent_folders()
        self.pinned_folders = await self._folders.pinned_folders()
        self._favorites = await self._library.favorites()
        self.theme_mode = await self._settings.theme_mode()
        self.lyric_font = await self._settings.lyric_font()
        self._apply_desktop_config(await self._desktop.restore())
        self.notify()

        if startup_path is None:
            return
        load = self._library.resolve_startup(startup_path)
        if load is None:
            return
        folder = startup_path.parent if startup_path.is_file() else startup_path
        await self._apply_tracks(
            load.tracks,
            play_index=load.play_index,
            autoplay=load.autoplay,
            source_folder=folder,
        )

    def shutdown(self) -> None:
        """释放引擎与悬浮窗资源（页面断开时调用）。"""
        self._sleep.cancel()
        self._playback.shutdown()
        self._desktop.stop()

    # ────────────────────────────────────────────────
    #  主题
    # ────────────────────────────────────────────────

    def cycle_theme(self) -> None:
        """浅色 → 深色 → 跟随系统 循环切换，并持久化。"""
        index = THEME_MODES.index(self.theme_mode)
        self.theme_mode = THEME_MODES[(index + 1) % len(THEME_MODES)]
        self._spawn(self._settings.save_theme_mode(self.theme_mode))
        self.notify()

    def set_system_brightness(self, brightness: str) -> None:
        """跟随系统亮度变化（仅在 ``system`` 模式下影响配色）。"""
        if brightness != self.system_brightness:
            self.system_brightness = brightness
            self.notify()

    # ────────────────────────────────────────────────
    #  列表：搜索 / 筛选 / 选中 / 收藏
    # ────────────────────────────────────────────────

    def set_search(self, value: str) -> None:
        """更新搜索词。"""
        if value != self.search:
            self.search = value
            self.notify()

    def set_favorites_only(self, value: bool) -> None:
        """切换「仅显示收藏」。"""
        if value != self.show_favorites:
            self.show_favorites = value
            self.notify()

    def select(self, track: Track) -> None:
        """单击列表项：只改选中项，不打断正在播放的歌曲。"""
        index = self._index_of(track)
        if index < 0:
            return
        self.selected = index
        self._refresh_display()
        self.notify()

    async def play(self, track: Track) -> None:
        """双击列表项：真正切歌播放。"""
        index = self._index_of(track)
        if index < 0:
            return
        await self._playback.play_at(index)

    async def toggle_favorite(self, track: Track) -> None:
        """切换收藏状态并持久化。"""
        key = track_key(track.path)
        track.favorite = not track.favorite
        if track.favorite:
            self._favorites.add(key)
        else:
            self._favorites.discard(key)
        await self._library.save_favorites(self._favorites)
        self.notify()

    # ────────────────────────────────────────────────
    #  播放控制
    # ────────────────────────────────────────────────

    async def toggle_play(self) -> None:
        """播放 / 暂停。"""
        await self._playback.toggle()

    async def next_track(self) -> None:
        """下一曲。"""
        await self._playback.next()

    async def previous_track(self) -> None:
        """上一曲。"""
        await self._playback.prev()

    async def seek(self, seconds: float) -> None:
        """跳转到指定秒数。"""
        await self._playback.seek(seconds)
        self.position = seconds
        self.notify()

    def set_volume(self, value: float) -> None:
        """设置音量。"""
        self.volume = max(0.0, min(1.0, float(value)))
        self._playback.set_volume(self.volume)
        self.notify()

    def set_speed(self, value: float) -> None:
        """设置播放倍速。"""
        self.speed = float(value)
        self._playback.set_speed(self.speed)
        self.notify()

    def cycle_mode(self) -> None:
        """切换播放模式（顺序 → 单曲 → 随机）。"""
        self.mode = self._playback.cycle_mode()
        self.notify()

    # ────────────────────────────────────────────────
    #  歌词
    # ────────────────────────────────────────────────

    def adjust_lyric_offset(self, delta: float) -> None:
        """歌词微调：正偏移提前显示，负偏移延后显示，并按曲目持久化。"""
        self.lyric_offset = round(self.lyric_offset + delta, 3)
        track = self.display_track
        if track is not None:
            self._spawn(self._lyrics.set_offset(track, self.lyric_offset))
        self.notify()

    def adjust_lyric_font(self, delta: float) -> None:
        """歌词字号 ±1px 步进，夹紧到合法范围并全局持久化。"""
        self.lyric_font = clamp_lyric_font(self.lyric_font + delta)
        self._spawn(self._settings.save_lyric_font(self.lyric_font))
        self.notify()

    # ────────────────────────────────────────────────
    #  桌面歌词
    # ────────────────────────────────────────────────

    def toggle_desktop_lyric(self) -> None:
        """开关桌面歌词；开启且当前无歌词时给一次提示。"""
        if not self.desktop_enabled and not self.lyrics:
            self.show_toast("当前歌曲暂无歌词，换上带歌词的歌曲会自动显示")
        self._desktop.toggle_visible()

    def toggle_desktop_lock(self) -> None:
        """锁定 / 解锁桌面歌词（锁定 = 鼠标穿透）。"""
        self._desktop.toggle_locked()

    def step_desktop_font(self, direction: float) -> None:
        """桌面歌词字号增减一档。"""
        self._desktop.nudge_font(DESKTOP_LYRIC_FONT_STEP * direction)

    def reset_desktop_font(self) -> None:
        """恢复桌面歌词默认字号。"""
        self._desktop.reset_font()

    def close_desktop_lyric(self) -> None:
        """关闭桌面歌词悬浮窗。"""
        self._desktop.set_visible(False)

    # ────────────────────────────────────────────────
    #  音乐库 / 文件夹历史
    # ────────────────────────────────────────────────

    async def import_music_folder(self) -> None:
        """弹出目录选择框并导入其中的音乐。"""
        folder = await self._library.choose_music_folder()
        if folder is None:
            return
        files = self._library.load_directory(folder)
        if not files:
            return
        await self._apply_tracks(files, source_folder=folder)

    async def open_recent_folder(self, folder: str) -> None:
        """打开历史文件夹。"""
        path = Path(folder)
        if not path.exists() or not path.is_dir():
            self.show_toast("历史文件夹已不存在")
            return
        files = self._library.load_directory(path)
        if not files:
            self.show_toast("该文件夹没有可播放的音乐")
            return
        await self._apply_tracks(files, source_folder=path)
        self.show_toast(f"已打开：{path.name or path}")

    async def toggle_pin_folder(self, folder: str) -> None:
        """固定 / 取消固定某个文件夹。"""
        self.pinned_folders = await self._folders.toggle_pinned(folder)
        self.notify()

    async def clear_recent_history(self) -> None:
        """清空最近打开记录（保留固定文件夹）。"""
        await self._folders.clear_recent_folders()
        self.recent_folders = []
        self.notify()
        self.show_toast("已清空历史记录")

    async def _apply_tracks(
        self,
        files: list[Track],
        *,
        play_index: int = 0,
        autoplay: bool = False,
        source_folder: Path | None = None,
    ) -> None:
        """导入一份曲目列表（内部入口）。

        ``self.tracks`` 必须先于 ``play_at`` 落位：切歌回调会立刻同步歌词，
        而歌词的来源正是 ``tracks[current]``。
        """
        self._favorites = await self._library.favorites()
        apply_favorites(files, self._favorites)
        self.tracks = files
        self.selected = play_index if files else -1
        self._playback.set_tracks(files)

        if autoplay and 0 <= play_index < len(files):
            await self._playback.play_at(play_index)

        if source_folder is not None:
            self.recent_folders = await self._folders.remember_folder(
                str(source_folder)
            )

        if autoplay and 0 <= play_index < len(files):
            self.position = 0.0
            self.duration = files[play_index].duration
        else:
            self.current = -1
            self.position = 0.0
            self.duration = files[play_index].duration if files else 0.0
            self.is_playing = False
        # 换了一整份列表，展示的曲目也跟着换了：歌词与按曲目的偏移都要重取
        self._refresh_display()
        self.notify()

    # ────────────────────────────────────────────────
    #  睡眠定时器
    # ────────────────────────────────────────────────

    def start_sleep_timer(self, total: float) -> None:
        """启动倒计时；再次调用会重置。"""
        self._sleep.start(float(total))

    def cancel_sleep_timer(self) -> None:
        """取消倒计时。"""
        self._sleep.cancel()
        self.sleep_remaining = 0.0
        self.notify()

    # ────────────────────────────────────────────────
    #  提示
    # ────────────────────────────────────────────────

    def show_toast(self, message: str) -> None:
        """弹一条一次性提示。"""
        self._toast_serial += 1
        self.toast = Toast(message=message, serial=self._toast_serial)
        self.notify()

    # ────────────────────────────────────────────────
    #  服务回调（PlaybackObserver）
    # ────────────────────────────────────────────────

    def on_position(self, seconds: float) -> None:
        self.position = seconds
        self.notify()

    def on_duration(self, seconds: float) -> None:
        self.duration = seconds
        self.notify()

    def on_play_state(self, playing: bool) -> None:
        self.is_playing = playing
        self.notify()

    def on_track_change(self, index: int) -> None:
        self.current = index
        self.selected = index
        self._refresh_display()
        self.notify()
        self._spawn(self._ensure_lyrics(index))

    # ────────────────────────────────────────────────
    #  悬浮窗回调（DesktopLyricListener）
    # ────────────────────────────────────────────────

    def on_desktop_command(self, name: str) -> None:
        """悬浮窗上的播放控制键（已由组装根投递回事件循环）。"""
        if name == "toggle":
            self._spawn(self._playback.toggle())
        elif name == "next":
            self._spawn(self._playback.next())
        elif name == "prev":
            self._spawn(self._playback.prev())

    def on_desktop_config(self, config: DesktopLyricConfig) -> None:
        """悬浮窗配置变化 → 同步到界面状态。"""
        self._apply_desktop_config(config)

    # ────────────────────────────────────────────────
    #  内部工具
    # ────────────────────────────────────────────────

    def notify(self) -> None:
        """广播状态变化；顺带把最新画面推给桌面歌词悬浮窗。"""
        desktop = getattr(self, "_desktop", None)
        if desktop is not None:
            desktop.push(
                self.desktop_lyric_lines, self.active_lyric_index, self.is_playing
            )
        super().notify()

    def _apply_desktop_config(self, config: DesktopLyricConfig) -> None:
        self.desktop_enabled = config.enabled
        self.desktop_locked = config.locked
        self.desktop_font = config.font_size
        self.notify()

    def _on_sleep_tick(self, remaining: float) -> None:
        self.sleep_remaining = remaining
        self.notify()

    def _on_sleep_elapsed(self) -> None:
        self.sleep_remaining = 0.0
        self.notify()
        if self._on_close_requested is not None:
            self._on_close_requested()

    def _index_of(self, track: Track) -> int:
        try:
            return self.tracks.index(track)
        except ValueError:
            return -1

    def _refresh_display(self) -> None:
        """当前展示的曲目变了：重取歌词与「按曲目记忆」的歌词偏移。

        这两个量在旧实现里是同一个 effect（依赖 ``current``/``selected``/
        ``tracks``），因此只要展示的曲目可能变了就必须一起刷新——包括导入
        整个文件夹、打开历史文件夹、按目录启动这些「列表整体替换」的路径。
        """
        self._sync_lyrics()
        self._spawn(self._sync_offset())

    def _sync_lyrics(self) -> None:
        """按当前展示的曲目重新加载歌词。"""
        track = self.display_track
        if track is None or track.lyrics_path is None:
            self.lyrics = []
            return
        self.lyrics = self._lyrics.load(track.lyrics_path)

    async def _sync_offset(self) -> None:
        """切歌后从持久化中恢复该曲目的歌词微调偏移。"""
        self.lyric_offset = await self._lyrics.offset_for(self.display_track)
        self.notify()

    async def _ensure_lyrics(self, index: int) -> None:
        """曲目缺歌词时后台补齐，并在仍是当前曲目时刷新歌词区。"""
        if not (0 <= index < len(self.tracks)):
            return
        track = self.tracks[index]
        lines = await self._lyrics.fetch_missing(track)
        if lines is None:
            return
        if self.current < 0 or self.tracks[self.current] is not track:
            return
        self.lyrics = lines
        self.notify()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """在事件循环上跑一个后台协程，并持有引用防止被 GC 回收。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            return
        task = loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
