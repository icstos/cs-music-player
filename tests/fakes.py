"""测试用的假实现：把基础设施层替换成内存版本。

这些替身让 service / viewmodel 两层的测试完全离线：不碰网络、不读音频文件、
不建窗口、不需要 Flet。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from collections.abc import Mapping, Sequence
from pathlib import Path

from cs_music_player.models import (
    AudioMetadata,
    DesktopLyricConfig,
    LyricLine,
    TagText,
    Track,
)


class FakePreferences:
    """内存键值存储，实现 ``PreferencesPort``。"""

    def __init__(self, data: dict | None = None) -> None:
        self.data: dict = dict(data or {})

    async def get(self, key: str) -> Any:
        return self.data.get(key)

    async def set(self, key: str, value: Any) -> None:
        self.data[key] = value


class FakeMetadata:
    """可控的 ``MetadataPort``：路径里带 ``|`` 的数字当作时长。"""

    def __init__(
        self,
        *,
        duration: float = 180.0,
        artist: str = "测试歌手",
        album: str = "测试专辑",
        cover: str | None = None,
    ) -> None:
        self.duration = duration
        self.artist = artist
        self.album = album
        self.cover = cover
        self.tags = TagText()
        self.read_count = 0

    def read(self, path: Path) -> AudioMetadata:
        self.read_count += 1
        return AudioMetadata(
            duration=self.duration,
            artist=self.artist,
            album=self.album,
            sample_rate=44100,
            bitrate=320000,
            channels=2,
        )

    def cover_data_uri(self, path: Path) -> str | None:
        return self.cover

    def read_tag_text(self, path: Path) -> TagText:
        return self.tags


class FakeLyricsRepository:
    """内存歌词仓库：``files`` 是路径 -> 歌词行。"""

    def __init__(self, files: Mapping[Path, list[LyricLine]] | None = None) -> None:
        self.files: dict[Path, list[LyricLine]] = dict(files or {})
        self.read_count = 0

    def index(self, lyrics_dir: Path) -> dict[str, Path]:
        result: dict[str, Path] = {}
        for path in self.files:
            if path.parent == lyrics_dir:
                result[path.stem.lower()] = path
        return result

    def match(self, index: Mapping[str, Path], stem: str) -> Path | None:
        return index.get(stem.lower())

    def read(self, path: Path) -> list[LyricLine]:
        self.read_count += 1
        return list(self.files.get(path, []))


class FakeLyricsProvider:
    """可编程的在线歌词源。"""

    def __init__(self, result: Path | None = None) -> None:
        self.result = result
        self.calls: list[Track] = []
        self.gate = None

    async def download(self, track: Track) -> Path | None:
        self.calls.append(track)
        if self.gate is not None:
            await self.gate.wait()
        return self.result


class FakeEngine:
    """内存音频引擎：记录调用序列。"""

    def __init__(self, observer: Any, *, playing: bool = False) -> None:
        self.observer = observer
        self._playing = playing
        self.loads: list[Path] = []
        self.pauses: list[bool] = []
        self.seeks: list[float] = []
        self.volume = 0.7
        self.speed = 1.0
        self.disposed = False

    @property
    def playing(self) -> bool:
        return self._playing

    def set_volume(self, value: float) -> None:
        self.volume = value

    def set_speed(self, value: float) -> None:
        self.speed = value

    async def load(self, path: Path, *, autoplay: bool = True) -> None:
        self.loads.append(path)
        if autoplay:
            self._playing = True
            self.observer.on_play_state(True)

    async def set_paused(self, paused: bool) -> None:
        self.pauses.append(paused)
        self._playing = not paused

    async def seek(self, seconds: float) -> None:
        self.seeks.append(seconds)

    def dispose(self) -> None:
        self.disposed = True


def engine_factory(**kwargs: Any) -> Any:
    """返回一个 ``EngineFactory``，并把造出来的引擎存到 ``created``。"""
    created: list[FakeEngine] = []

    def factory(observer: Any) -> FakeEngine:
        engine = FakeEngine(observer, **kwargs)
        created.append(engine)
        return engine

    factory.created = created  # type: ignore[attr-defined]
    return factory


class FakePicker:
    """固定返回一个目录的 ``DirectoryPickerPort``。"""

    def __init__(self, directory: str | None = None) -> None:
        self.directory = directory
        self.calls: list[str] = []

    async def pick_directory(self, title: str) -> str | None:
        self.calls.append(title)
        return self.directory


class FakeDesktopLyric:
    """内存悬浮窗，实现 ``DesktopLyricPort``。"""

    def __init__(self, config: DesktopLyricConfig | None = None) -> None:
        self._config = config or DesktopLyricConfig()
        self.lyrics: list[str] = []
        self.active = -1
        self.playing = False
        self.stopped = False
        self.centered = False

    @property
    def config(self) -> DesktopLyricConfig:
        return self._config

    def apply_config(self, config: DesktopLyricConfig) -> None:
        self._config = config

    def set_lyrics(self, lines: Sequence[str]) -> None:
        self.lyrics = list(lines)

    def set_active(self, index: int) -> None:
        self.active = index

    def set_playing(self, playing: bool) -> None:
        self.playing = playing

    def set_visible(self, visible: bool) -> None:
        self._config.enabled = bool(visible)

    def set_locked(self, locked: bool, *, hint: bool = True) -> None:
        self._config.locked = bool(locked)

    def set_font_size(self, size: float) -> None:
        self._config.font_size = float(size)

    def center(self) -> None:
        self.centered = True

    def stop(self) -> None:
        self.stopped = True


class RecordingObserver:
    """记录播放回调的 ``PlaybackObserver``。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def on_position(self, seconds: float) -> None:
        self.events.append(("position", seconds))

    def on_duration(self, seconds: float) -> None:
        self.events.append(("duration", seconds))

    def on_play_state(self, playing: bool) -> None:
        self.events.append(("playing", playing))

    def on_track_change(self, index: int) -> None:
        self.events.append(("track", index))

    def names(self) -> list[str]:
        return [name for name, _ in self.events]


def write_offset_prefs(**offsets: float) -> FakePreferences:
    """构造一份带歌词偏移的偏好存储（键为曲目绝对路径）。"""
    return FakePreferences({"lyric_offsets": json.dumps(offsets)})


def make_view_model(
    *,
    metadata: FakeMetadata | None = None,
    repository: FakeLyricsRepository | None = None,
    provider: FakeLyricsProvider | None = None,
    preferences: FakePreferences | None = None,
    picker: FakePicker | None = None,
    desktop: FakeDesktopLyric | None = None,
    engine: Any = None,
    on_close: Callable[[], None] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """用假基础设施装配一个完整的视图模型（离线、无 Flet）。

    Returns:
        ``(view_model, parts)``；``parts`` 里带着各层替身，便于断言。
    """
    from cs_music_player.service.desktop_lyric import DesktopLyricService
    from cs_music_player.service.folders import FolderHistoryService
    from cs_music_player.service.library import LibraryService
    from cs_music_player.service.lyrics import LyricsService
    from cs_music_player.service.playback import PlaybackService
    from cs_music_player.service.settings import SettingsService
    from cs_music_player.viewmodel import AppViewModel

    metadata = metadata or FakeMetadata()
    repository = repository or FakeLyricsRepository()
    provider = provider or FakeLyricsProvider()
    preferences = preferences or FakePreferences()
    picker = picker or FakePicker()
    desktop_port = desktop or FakeDesktopLyric()

    settings = SettingsService(preferences)
    library = LibraryService(metadata, repository, preferences, picker)
    folders = FolderHistoryService(preferences)
    lyrics = LyricsService(repository, provider, preferences)
    desktop_service = DesktopLyricService(
        lambda on_command, on_config: desktop_port, settings
    )
    factory = engine if engine is not None else engine_factory()

    def playback_factory(observer: Any) -> PlaybackService:
        return PlaybackService(factory, observer)

    view_model = AppViewModel(
        playback_factory=playback_factory,
        library=library,
        folders=folders,
        lyrics=lyrics,
        settings=settings,
        desktop_lyric=desktop_service,
        on_close_requested=on_close,
    )
    parts = {
        "metadata": metadata,
        "repository": repository,
        "provider": provider,
        "preferences": preferences,
        "picker": picker,
        "desktop": desktop_port,
        "engine": factory.created[0] if getattr(factory, "created", None) else None,
        "library": library,
        "folders": folders,
        "lyrics": lyrics,
        "settings": settings,
    }
    return view_model, parts