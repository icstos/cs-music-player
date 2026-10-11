"""音乐库服务：目录选择、扫描、曲目构建与收藏。

只依赖 ``MetadataPort`` / ``LyricsRepositoryPort`` / ``DirectoryPickerPort``
/ ``PreferencesPort``；这里放的是**业务规则**（扫描范围、收藏语义），技术
实现全部由基础设施层提供。文件夹历史另见
:mod:`cs_music_player.service.folders`。
"""

from __future__ import annotations

from pathlib import Path

from ..infra.ports import (
    FAVORITES_KEY,
    DirectoryPickerPort,
    LyricsRepositoryPort,
    MetadataPort,
    PreferencesPort,
)
from ..models import AUDIO_EXTENSIONS, StartupLoad, Track, track_key

__all__ = ["LibraryService", "apply_favorites", "filter_tracks"]


def apply_favorites(tracks: list[Track], favorites: set[str]) -> None:
    """就地把收藏状态刷到曲目列表上。"""
    for track in tracks:
        track.favorite = track_key(track.path) in favorites


def filter_tracks(
    tracks: list[Track], query: str, *, favorites_only: bool = False
) -> list[Track]:
    """按歌名 / 歌手 / 所在文件夹名过滤曲目（可选「仅收藏」）。"""
    needle = query.lower()
    result: list[Track] = []
    for track in tracks:
        if favorites_only and not track.favorite:
            continue
        if needle and not (
            needle in track.title.lower()
            or needle in track.artist.lower()
            or needle in track.path.parent.name.lower()
        ):
            continue
        result.append(track)
    return result


class LibraryService:
    """曲目导入与收藏的业务流程。

    Args:
        metadata: 音频元数据与封面读取。
        lyrics: 本地歌词索引 / 匹配。
        preferences: 持久化收藏。
        picker: 目录选择框（可选；未装配时 :meth:`choose_music_folder` 返回 ``None``）。
    """

    def __init__(
        self,
        metadata: MetadataPort,
        lyrics: LyricsRepositoryPort,
        preferences: PreferencesPort,
        picker: DirectoryPickerPort | None = None,
    ) -> None:
        self._metadata = metadata
        self._lyrics = lyrics
        self._prefs = preferences
        self._picker = picker

    # —— 目录选择 —— #

    async def choose_music_folder(self, title: str = "选择音乐文件夹") -> Path | None:
        """弹出系统目录选择框；用户取消或未装配选择器时返回 ``None``。"""
        if self._picker is None:
            return None
        raw = await self._picker.pick_directory(title)
        if not raw:
            return None
        return Path(raw)

    # —— 曲目构建 —— #

    def load_directory(self, directory: Path) -> list[Track]:
        """扫描目录**根层级**的音频文件（不递归子目录）。"""
        index = self._lyrics.index(directory / "lyrics")
        tracks: list[Track] = []
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return []
        for path in entries:
            if not (path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS):
                continue
            tracks.append(self._build(path, index))
        return tracks

    def create_track(self, path: Path) -> Track | None:
        """从单个音频文件创建曲目；格式不支持时返回 ``None``。"""
        resolved = path.resolve()
        if not resolved.is_file() or resolved.suffix.lower() not in AUDIO_EXTENSIONS:
            return None
        index = self._lyrics.index(resolved.parent / "lyrics")
        return self._build(resolved, index)

    def _build(self, path: Path, index: dict[str, Path]) -> Track:
        info = self._metadata.read(path)
        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0
        return Track(
            path=path,
            artist=info.artist,
            duration=info.duration,
            lyrics_path=self._lyrics.match(index, path.stem),
            cover_src=self._metadata.cover_data_uri(path),
            album=info.album,
            file_size=file_size,
            sample_rate=info.sample_rate,
            bitrate=info.bitrate,
            channels=info.channels,
        )

    def resolve_startup(self, path: Path) -> StartupLoad | None:
        """根据启动路径解析曲目：文件则加载同目录并播放该曲，目录则仅导入。"""
        resolved = path.expanduser().resolve()
        if resolved.is_dir():
            tracks = self.load_directory(resolved)
            if not tracks:
                return None
            return StartupLoad(tracks, 0, False)

        track = self.create_track(resolved)
        if track is None:
            return None

        tracks = self.load_directory(resolved.parent)
        if not tracks:
            return StartupLoad([track], 0, True)

        play_index = self._index_of(tracks, track)
        if play_index < 0:
            tracks = sorted([*tracks, track], key=lambda item: item.path.name.lower())
            play_index = self._index_of(tracks, track)
        return StartupLoad(tracks, play_index, True)

    @staticmethod
    def _index_of(tracks: list[Track], target: Track) -> int:
        wanted = target.path.resolve()
        for i, item in enumerate(tracks):
            if item.path.resolve() == wanted:
                return i
        return -1

    # —— 收藏 —— #

    async def favorites(self) -> set[str]:
        """读取收藏集合。"""
        raw = await self._prefs.get(FAVORITES_KEY)
        return set(raw or [])

    async def save_favorites(self, favorites: set[str]) -> None:
        """保存收藏集合。"""
        await self._prefs.set(FAVORITES_KEY, sorted(favorites))
