"""视图模型：状态派生、动作编排与持久化的端到端（全离线）。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cs_music_player.models import (
    LYRIC_FONT_DEFAULT,
    ColorTheme,
    LyricLine,
    ThemeMode,
    Track,
)

from fakes import (
    FakeDesktopLyric,
    FakeLyricsProvider,
    FakeLyricsRepository,
    FakePreferences,
    FakePicker,
    make_view_model,
)


def _write_songs(folder: Path, names: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"x")


# ── 导入与派生 ── #


def test_import_folder_loads_tracks_and_remembers_history(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.flac", "notes.txt"])
    vm, parts = make_view_model(picker=FakePicker(str(folder)))

    asyncio.run(vm.import_music_folder())

    assert [t.title for t in vm.tracks] == ["a", "b"]
    assert vm.recent_folders == [str(folder.resolve())]
    assert vm.playlist_count == 2
    assert vm.current == -1
    assert vm.selected == 0


def test_import_is_a_noop_when_the_picker_is_cancelled(tmp_path: Path) -> None:
    vm, _ = make_view_model(picker=FakePicker(None))

    asyncio.run(vm.import_music_folder())

    assert vm.tracks == []


def test_search_and_favorites_filter_are_derived_state() -> None:
    vm, _ = make_view_model()
    tracks = [
        Track(path=Path("a.mp3"), title="晴天", artist="周杰伦"),
        Track(path=Path("b.mp3"), title="夜曲", artist="周杰伦"),
        Track(path=Path("c.mp3"), title="Yellow", artist="Coldplay"),
    ]
    vm.tracks = tracks
    tracks[1].favorite = True

    vm.set_search("周杰伦")
    assert vm.filtered_tracks == [tracks[0], tracks[1]]

    vm.set_search("")
    vm.set_favorites_only(True)
    assert vm.filtered_tracks == [tracks[1]]

    vm.set_favorites_only(False)
    assert vm.filtered_tracks == tracks


def test_filtered_selected_reports_index_in_the_filtered_list() -> None:
    vm, _ = make_view_model()
    tracks = [Track(path=Path(f"{i}.mp3"), title=f"song {i}") for i in range(3)]
    vm.tracks = tracks
    vm.selected = 2
    vm.set_search("song 2")

    assert vm.filtered_tracks == [tracks[2]]
    assert vm.filtered_selected == 0


def test_selection_outside_the_filter_reports_minus_one() -> None:
    vm, _ = make_view_model()
    tracks = [Track(path=Path(f"{i}.mp3"), title=f"song {i}") for i in range(3)]
    vm.tracks = tracks
    vm.selected = 0
    vm.set_search("song 2")

    assert vm.filtered_selected == -1


# ── 收藏 ── #


def test_toggle_favorite_mutates_and_persists() -> None:
    prefs = FakePreferences()
    vm, parts = make_view_model(preferences=prefs)
    track = Track(path=Path("a.mp3"), title="A")
    vm.tracks = [track]

    asyncio.run(vm.toggle_favorite(track))

    assert track.favorite is True
    assert prefs.data["favorite_tracks"] == [str(track.path.resolve())]

    asyncio.run(vm.toggle_favorite(track))
    assert track.favorite is False
    assert prefs.data["favorite_tracks"] == []


def test_import_applies_stored_favorites() -> None:
    vm, _ = make_view_model()
    track = Track(path=Path("a.mp3"))
    prefs_key = str(track.path.resolve())
    vm, parts = make_view_model(
        preferences=FakePreferences({"favorite_tracks": [prefs_key]})
    )

    asyncio.run(vm._apply_tracks([track]))

    assert track.favorite is True


def test_import_folder_restores_the_first_tracks_lyric_offset() -> None:
    """回归：换整份列表（导入 / 打开历史 / 按目录启动）也要刷新歌词偏移。

    旧实现的偏移恢复是一个依赖 ``[current, selected, tracks]`` 的 effect，
    任何 ``tracks`` 变化都会触发；只挂在「选曲」与「切歌」上会漏掉导入路径。
    """
    first = Track(path=Path("music/a.mp3"))
    second = Track(path=Path("music/b.mp3"))
    prefs = FakePreferences(
        {"lyric_offsets": json.dumps({str(first.path.resolve()): 0.7})}
    )
    vm, _ = make_view_model(preferences=prefs)

    async def flow() -> None:
        await vm._apply_tracks([first, second], play_index=0, autoplay=False)
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # 让偏移读取的后台任务跑完

    asyncio.run(flow())

    assert vm.current == -1
    assert vm.selected == 0
    assert vm.lyric_offset == 0.7


def test_directory_startup_restores_lyric_offset(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.mp3"])
    prefs = FakePreferences(
        {"lyric_offsets": json.dumps({str((folder / "a.mp3").resolve()): -0.3})}
    )
    vm, _ = make_view_model(preferences=prefs)

    asyncio.run(vm.initialize(folder))

    assert vm.lyric_offset == -0.3


def test_import_clears_a_stale_offset_from_the_previous_list(tmp_path: Path) -> None:
    """回归：新列表里没有被记住的偏移时，必须回到 0，而不是沿用上一首的值。"""
    folder = tmp_path / "music"
    _write_songs(folder, ["new.mp3"])
    vm, _ = make_view_model(picker=FakePicker(str(folder)))
    vm.lyric_offset = 9.0  # 模拟上一份列表遗留下来的偏移

    async def flow() -> None:
        await vm.import_music_folder()
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # 让偏移读取的后台任务跑完

    asyncio.run(flow())

    assert vm.lyric_offset == 0.0


# ── 主题 ── #


def test_cycle_theme_walks_light_dark_system_and_persists() -> None:
    prefs = FakePreferences()
    vm, _ = make_view_model(preferences=prefs)
    assert vm.theme_mode == ThemeMode.SYSTEM

    async def flow() -> list[ThemeMode]:
        seen: list[ThemeMode] = []
        for _ in range(3):
            vm.cycle_theme()
            seen.append(vm.theme_mode)
            await asyncio.sleep(0)  # 让持久化任务跑完
        return seen

    assert asyncio.run(flow()) == [ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.SYSTEM]
    assert prefs.data["theme_mode"] == "system"


def test_effective_theme_follows_system_brightness() -> None:
    vm, _ = make_view_model()
    assert vm.effective_theme == ThemeMode.LIGHT
    vm.set_system_brightness("dark")
    assert vm.effective_theme == ThemeMode.DARK

    vm.theme_mode = ThemeMode.LIGHT
    assert vm.effective_theme == ThemeMode.LIGHT


def test_set_theme_mode_persists_and_ignores_repeats() -> None:
    prefs = FakePreferences({"theme_mode": "dark"})
    vm, _ = make_view_model(preferences=prefs)

    async def flow() -> None:
        vm.set_theme_mode(ThemeMode.DARK)  # 与当前一致 → 不写盘
        await asyncio.sleep(0)
        vm.set_theme_mode(ThemeMode.LIGHT)
        await asyncio.sleep(0)

    vm.theme_mode = ThemeMode.DARK
    prefs.data["theme_mode"] = "dark"
    asyncio.run(flow())

    assert vm.theme_mode == ThemeMode.LIGHT
    assert prefs.data["theme_mode"] == "light"


def test_color_theme_defaults_to_business_blue() -> None:
    vm, _ = make_view_model()
    assert vm.color_theme == ColorTheme.BUSINESS_BLUE


def test_set_color_theme_persists_without_touching_mode() -> None:
    prefs = FakePreferences()
    vm, _ = make_view_model(preferences=prefs)
    vm.theme_mode = ThemeMode.DARK

    async def flow() -> None:
        vm.set_color_theme(ColorTheme.LAVENDER)
        await asyncio.sleep(0)

    asyncio.run(flow())

    assert vm.color_theme == ColorTheme.LAVENDER
    assert prefs.data["color_theme"] == "lavender"
    # 薰衣草紫没有明暗倾向：外观保持不变
    assert vm.theme_mode == ThemeMode.DARK


def test_midnight_switches_appearance_to_dark_and_white_to_light() -> None:
    prefs = FakePreferences()
    vm, _ = make_view_model(preferences=prefs)
    vm.theme_mode = ThemeMode.LIGHT

    async def flow() -> None:
        vm.set_color_theme(ColorTheme.MIDNIGHT)  # 暗夜黑 → 顺带切深色
        await asyncio.sleep(0)
        vm.set_color_theme(ColorTheme.MINIMAL_WHITE)  # 极简白 → 顺带切浅色
        await asyncio.sleep(0)

    asyncio.run(flow())

    assert vm.color_theme == ColorTheme.MINIMAL_WHITE
    assert vm.theme_mode == ThemeMode.LIGHT
    assert prefs.data["theme_mode"] == "light"


def test_initialize_restores_persisted_color_theme() -> None:
    prefs = FakePreferences({"color_theme": "tiffany", "theme_mode": "dark"})
    vm, _ = make_view_model(preferences=prefs)

    asyncio.run(vm.initialize())

    assert vm.color_theme == ColorTheme.TIFFANY
    assert vm.theme_mode == ThemeMode.DARK


def test_unknown_persisted_color_theme_falls_back() -> None:
    vm, _ = make_view_model(preferences=FakePreferences({"color_theme": "neon"}))

    asyncio.run(vm.initialize())

    assert vm.color_theme == ColorTheme.BUSINESS_BLUE


# ── 歌词 ── #


def test_select_loads_lyrics_and_offset_for_the_track() -> None:
    folder = Path("music")
    lyrics_path = folder / "lyrics" / "a.lrc"
    lines = [LyricLine(time=1.0, text="hello")]
    repository = FakeLyricsRepository({lyrics_path: lines})
    prefs = FakePreferences(
        {"lyric_offsets": json.dumps({str((folder / "a.mp3").resolve()): 0.4})}
    )
    vm, _ = make_view_model(repository=repository, preferences=prefs)
    track = Track(path=folder / "a.mp3", lyrics_path=lyrics_path)
    vm.tracks = [track]

    async def flow() -> None:
        vm.select(track)
        await asyncio.sleep(0)  # 让偏移读取的后台任务跑完

    asyncio.run(flow())

    assert vm.lyrics == lines
    assert vm.has_lyrics is True
    assert vm.lyric_offset == 0.4


def test_adjust_lyric_offset_persists_per_track() -> None:
    prefs = FakePreferences()
    vm, _ = make_view_model(preferences=prefs)
    track = Track(path=Path("a.mp3"))
    vm.tracks = [track]
    vm.selected = 0
    key = str(track.path.resolve())

    async def flow() -> None:
        vm.adjust_lyric_offset(0.1)
        vm.adjust_lyric_offset(0.1)
        await asyncio.sleep(0)
        assert vm.lyric_offset == 0.2
        assert json.loads(prefs.data["lyric_offsets"]) == {key: 0.2}

        vm.adjust_lyric_offset(-0.1)
        vm.adjust_lyric_offset(-0.1)
        await asyncio.sleep(0)

    asyncio.run(flow())

    # 偏移归零后记录被移除（写回空表）
    assert vm.lyric_offset == 0.0
    assert json.loads(prefs.data["lyric_offsets"]) == {}

def test_adjust_lyric_font_clamps_and_persists() -> None:
    prefs = FakePreferences()
    vm, _ = make_view_model(preferences=prefs)

    async def flow() -> None:
        vm.adjust_lyric_font(2)
        await asyncio.sleep(0)
        assert vm.lyric_font == LYRIC_FONT_DEFAULT + 2
        assert prefs.data["lyric_font"] == LYRIC_FONT_DEFAULT + 2

        for _ in range(50):
            vm.adjust_lyric_font(1)
        await asyncio.sleep(0)
        assert vm.lyric_font == 24.0

    asyncio.run(flow())


def test_active_lyric_index_tracks_position_and_offset() -> None:
    vm, _ = make_view_model()
    vm.lyrics = [LyricLine(time=0.0, text="a"), LyricLine(time=10.0, text="b")]

    vm.position = 0.0
    assert vm.active_lyric_index == 0
    vm.position = 11.0
    assert vm.active_lyric_index == 1

    # 偏移 +5s = 提前 5 秒：位置 4.0 时第 1 行已该高亮
    vm.position = 4.0
    vm.lyric_offset = 5.0
    assert vm.active_lyric_index == 0


def test_missing_lyrics_are_fetched_in_the_background() -> None:
    folder = Path("music")
    downloaded = folder / "lyrics" / "a.lrc"
    lines = [LyricLine(time=0.0, text="fetched")]
    repository = FakeLyricsRepository({downloaded: lines})
    provider = FakeLyricsProvider(result=downloaded)
    vm, parts = make_view_model(repository=repository, provider=provider)
    track = Track(path=folder / "a.mp3")

    async def flow() -> None:
        vm.tracks = [track]
        vm.on_track_change(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(flow())

    assert provider.calls == [track]
    assert track.lyrics_path == downloaded
    assert vm.lyrics == lines


def test_lyrics_are_not_overwritten_when_the_track_changed_meanwhile() -> None:
    folder = Path("music")
    downloaded = folder / "lyrics" / "a.lrc"
    repository = FakeLyricsRepository({downloaded: [LyricLine(0.0, "a")]})
    provider = FakeLyricsProvider(result=downloaded)
    vm, _ = make_view_model(repository=repository, provider=provider)
    first = Track(path=folder / "a.mp3")
    second = Track(path=folder / "b.mp3")

    async def flow() -> None:
        vm.tracks = [first, second]
        # 后台补齐的是第 0 首，但用户此刻已经切到第 1 首
        vm.current = 1
        await vm._ensure_lyrics(0)

    asyncio.run(flow())

    assert first.lyrics_path == downloaded  # 文件仍然补上了
    assert vm.lyrics == []  # 但歌词区不会被「别人的」歌词覆盖


# ── 桌面歌词 ── #


def test_desktop_toggle_syncs_mirrored_state() -> None:
    desktop = FakeDesktopLyric()
    vm, _ = make_view_model(desktop=desktop)

    vm.toggle_desktop_lyric()

    assert vm.desktop_enabled is True
    assert desktop.config.enabled is True
    assert vm.toast is not None  # 无歌词时给出提示


def test_desktop_config_pushes_lines_and_state() -> None:
    desktop = FakeDesktopLyric()
    vm, _ = make_view_model(desktop=desktop)
    vm.lyrics = [LyricLine(0.0, "a"), LyricLine(1.0, "b")]
    vm.position = 1.5

    vm.set_volume(0.5)

    assert desktop.lyrics == ["a", "b"]
    assert desktop.active == 1
    assert desktop.playing is False


def test_desktop_lock_and_font_are_reflected() -> None:
    desktop = FakeDesktopLyric()
    vm, _ = make_view_model(desktop=desktop)

    vm.toggle_desktop_lock()
    assert vm.desktop_locked is True

    vm.step_desktop_font(1.0)
    assert vm.desktop_font == 26.0 + 2.0

    vm.reset_desktop_font()
    assert vm.desktop_font == 26.0


def test_overlay_buttons_drive_playback(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.mp3"])
    vm, parts = make_view_model(picker=FakePicker(str(folder)))
    asyncio.run(vm.import_music_folder())
    asyncio.run(vm.play(vm.tracks[0]))

    async def flow() -> None:
        vm.on_desktop_command("next")
        await asyncio.sleep(0)

    asyncio.run(flow())

    assert vm.current == 1


# ── 睡眠定时器 ── #


def test_sleep_timer_resets_remaining_and_requests_shutdown() -> None:
    closed: list[bool] = []
    vm, _ = make_view_model(on_close=lambda: closed.append(True))

    async def flow() -> None:
        vm.start_sleep_timer(1)
        assert vm.sleep_remaining == 1.0
        await asyncio.sleep(1.6)

    asyncio.run(flow())

    assert vm.sleep_remaining == 0.0
    assert closed == [True]


def test_sleep_timer_can_be_cancelled() -> None:
    closed: list[bool] = []
    vm, _ = make_view_model(on_close=lambda: closed.append(True))

    async def flow() -> None:
        vm.start_sleep_timer(100)
        vm.cancel_sleep_timer()
        await asyncio.sleep(0.05)

    asyncio.run(flow())

    assert vm.sleep_remaining == 0.0
    assert closed == []


# ── 启动路径与持久化恢复 ── #


def test_initialize_restores_persisted_settings() -> None:
    desktop_settings = json.dumps(
        {"enabled": True, "locked": True, "font_size": 30.0, "x": 5.0, "y": 6.0}
    )
    prefs = FakePreferences(
        {
            "theme_mode": "dark",
            "lyric_font": 18.0,
            "recent_folders": ["C:/Music/A"],
            "pinned_folders": ["C:/Music/A"],
            "desktop_lyric": desktop_settings,
        }
    )
    desktop = FakeDesktopLyric()
    vm, _ = make_view_model(preferences=prefs, desktop=desktop)

    asyncio.run(vm.initialize())

    assert vm.theme_mode == ThemeMode.DARK
    assert vm.lyric_font == 18.0
    assert vm.recent_folders == ["C:/Music/A"]
    assert vm.pinned_folders == {"C:/Music/A"}
    assert vm.desktop_enabled is True
    assert vm.desktop_locked is True
    assert vm.desktop_font == 30.0
    assert desktop.config.enabled is True


def test_initialize_loads_the_startup_file_and_autoplays(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.mp3"])
    target = folder / "b.mp3"
    vm, parts = make_view_model()

    asyncio.run(vm.initialize(target))

    assert [t.title for t in vm.tracks] == ["a", "b"]
    assert vm.current == 1
    assert vm.selected == 1
    assert parts["engine"].loads == [target]
    assert vm.is_playing is True
    assert vm.recent_folders == [str(folder.resolve())]


def test_initialize_with_a_directory_imports_without_playing(tmp_path: Path) -> None:
    folder = tmp_path / "music"
    _write_songs(folder, ["a.mp3", "b.mp3"])
    vm, parts = make_view_model()

    asyncio.run(vm.initialize(folder))

    assert len(vm.tracks) == 2
    assert vm.current == -1
    assert parts["engine"].loads == []


def test_open_recent_folder_reports_missing_directory() -> None:
    vm, _ = make_view_model()
    vm.recent_folders = ["C:/definitely/not/here"]

    asyncio.run(vm.open_recent_folder("C:/definitely/not/here"))

    assert vm.toast is not None
    assert "不存在" in vm.toast.message


def test_pin_and_clear_history() -> None:
    vm, _ = make_view_model()
    vm.recent_folders = ["C:/Music/A"]

    asyncio.run(vm.toggle_pin_folder("C:/Music/A"))
    assert vm.pinned_folders == {str(Path("C:/Music/A").resolve())}

    asyncio.run(vm.clear_recent_history())
    assert vm.recent_folders == []
    assert vm.pinned_folders == {str(Path("C:/Music/A").resolve())}


# ── 可观测性 ── #


def test_subscribers_are_notified_and_can_unsubscribe() -> None:
    vm, _ = make_view_model()
    seen: list[int] = []
    unsubscribe = vm.subscribe(lambda: seen.append(1))

    vm.set_search("x")
    assert len(seen) == 1

    unsubscribe()
    vm.set_search("y")
    assert len(seen) == 1
    assert vm.listener_count == 0


def test_shutdown_releases_engine_and_overlay() -> None:
    desktop = FakeDesktopLyric()
    vm, parts = make_view_model(desktop=desktop)

    vm.shutdown()

    assert parts["engine"].disposed is True
    assert desktop.stopped is True
