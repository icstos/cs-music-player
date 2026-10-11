"""冒烟测试：元数据/封面读取、收藏与启动路径解析。

用法：``python scripts/smoke_test.py``（不依赖 Flet，可在无界面环境跑）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cs_music_player.infra.lyrics_repository import LocalLyricsRepository
from cs_music_player.infra.metadata import extract_cover_src
from cs_music_player.infra.startup_args import parse_startup_path
from cs_music_player.models import AudioMetadata, Track, track_key
from cs_music_player.service.library import LibraryService, apply_favorites

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _Preferences:
    """最小内存偏好存储（满足 PreferencesPort）。"""

    def __init__(self) -> None:
        self._data: dict = {}

    async def get(self, key: str) -> Any:
        return self._data.get(key)

    async def set(self, key: str, value: Any) -> None:
        self._data[key] = value


def main() -> None:
    metadata = _SmokeMetadata()
    library = LibraryService(metadata, LocalLyricsRepository(), _Preferences())

    mp3 = PROJECT_ROOT / "viper.mp3"
    track = None
    if mp3.exists():
        cover = extract_cover_src(mp3)
        print("viper.mp3 cover:", "yes" if cover else "no")
        if cover:
            print("  data-uri prefix:", cover[:40] + "...")
        tracks = library.load_directory(PROJECT_ROOT)
        print("tracks in root:", len(tracks))
        for item in tracks:
            print(
                " -",
                item.title,
                "cover=",
                bool(item.cover_src),
                "duration=",
                round(item.duration, 1),
            )
        track = tracks[0]
    else:
        print("viper.mp3 not found, skipping cover test")
        track = Track(path=PROJECT_ROOT / "sample.mp3", title="Sample")

    favorites = {track_key(track.path)}
    apply_favorites([track], favorites)
    assert track.favorite is True
    apply_favorites([track], set())
    assert track.favorite is False
    print("apply_favorites: ok")

    assert parse_startup_path(["--web", "missing.mp3"]) is None
    if mp3.exists():
        assert parse_startup_path(["--web", str(mp3)]) == mp3.resolve()
        load = library.resolve_startup(mp3)
        assert load is not None
        assert load.autoplay is True
        assert load.tracks
        assert load.tracks[load.play_index].path.resolve() == mp3.resolve()
        print("startup load:", load.tracks[load.play_index].title)
    print("startup helpers: ok")


class _SmokeMetadata:
    """真实 mutagen 读取（封面交给 extract_cover_src 单独验证）。"""

    def read(self, path: Path) -> AudioMetadata:
        from cs_music_player.infra.metadata import read_audio_info

        return read_audio_info(path)

    def cover_data_uri(self, path: Path) -> str | None:
        return extract_cover_src(path)


if __name__ == "__main__":
    main()
