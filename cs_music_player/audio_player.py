"""音频播放器核心：数据模型、曲目加载、播放控制。"""

from __future__ import annotations

import asyncio
import base64
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import flet as ft
import flet_audio as fa

from .constants import (
    MODE_ORDER,
    MODE_SEQUENCE,
    MODE_LOOP_ONE,
    MODE_SHUFFLE,
    SUPPORTED_FORMATS,
)
from .lyrics import build_lyrics_index, match_lyrics_path


# ── 数据模型 ── #


@dataclass
class Track:
    path: Path
    title: str = ""
    artist: str = ""
    duration: float = 0.0
    lyrics_path: Path | None = None
    favorite: bool = False
    cover_src: str | None = None
    album: str = ""
    file_size: int = 0
    sample_rate: int = 0
    bitrate: int = 0
    channels: int = 0
    audio_format: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.path.stem
        if not self.audio_format:
            self.audio_format = self.path.suffix[1:].upper() or "UNKNOWN"


@dataclass
class PlayerCallbacks:
    """播放器 → UI 的回调接口。"""

    on_position: Callable[[float], None]
    on_duration: Callable[[float], None]
    on_play_state: Callable[[bool], None]
    on_track_change: Callable[[int], None]


# ── 工具函数 ── #


def _audio_tags(path: Path):
    """打开音频文件并返回 (audio, tags)；失败返回 (None, None)。"""
    try:
        from mutagen import File

        audio = File(str(path))
    except Exception:
        return None, None
    tags = getattr(audio, "tags", None) if audio is not None else None
    return audio, tags


def _tag_value(tags, *keys: str) -> str:
    """从标签对象中按候选键读取文本值，优先级由参数顺序决定。"""
    if tags is None:
        return ""
    for key in keys:
        value = tags.get(key)
        if value is None:
            continue
        if hasattr(value, "text"):
            items = [str(i) for i in (value.text or [])]
        elif isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple)):
            items = [str(i) for i in value]
        else:
            items = [str(value)]
        text = " / ".join(i.strip("[]' \u3000") for i in items if i)
        if text:
            return text
    return ""


def get_track_duration(path: Path) -> float:
    """用 mutagen 读取音频时长（秒），失败返回 0。"""
    audio, _ = _audio_tags(path)
    if audio is not None and hasattr(audio, "info"):
        try:
            return float(audio.info.length)
        except Exception:
            pass
    return 0.0


def get_track_artist(path: Path) -> str:
    """用 mutagen 读取歌手/艺术家，缺失时返回空字符串。"""
    _, tags = _audio_tags(path)
    if tags is None:
        return ""
    return _tag_value(
        tags, "artist", "TPE1", "albumartist", "TPE2", "\xa9ART", "performer"
    )


def read_audio_info(path: Path) -> dict:
    """一次性读取曲目元数据：时长、歌手、专辑、采样率、码率、声道等。

    返回 dict，供 ``Track`` 构建时批量填充；读取失败返回空 dict。
    """
    audio, tags = _audio_tags(path)
    info = getattr(audio, "info", None) if audio is not None else None
    data: dict = {}
    if info is not None:
        try:
            if getattr(info, "length", None) is not None:
                data["duration"] = float(info.length)
        except Exception:
            pass
        for attr in ("sample_rate", "bitrate", "channels"):
            value = getattr(info, attr, None)
            if value:
                data[attr] = int(value)
    if tags is not None:
        album = _tag_value(tags, "album", "TALB", "\xa9alb", "ALBUM")
        if album:
            data["album"] = album
        artist = _tag_value(
            tags, "artist", "TPE1", "albumartist", "TPE2", "\xa9ART", "performer"
        )
        if artist:
            data["artist"] = artist
    return data


def extract_cover_src(path: Path) -> str | None:
    """从音频内嵌标签提取封面，返回 data URI；无封面时返回 None。"""
    try:
        import base64

        audio, _ = _audio_tags(path)
        if audio is None:
            return None

        data: bytes | None = None
        mime = "image/jpeg"

        if hasattr(audio, "pictures") and audio.pictures:
            pic = audio.pictures[0]
            data = pic.data
            mime = pic.mime or "image/jpeg"
        elif audio.tags:
            for tag in audio.tags.values():
                tag_data = getattr(tag, "data", None)
                if isinstance(tag_data, bytes):
                    data = tag_data
                    mime = getattr(tag, "mime", None) or "image/jpeg"
                    break

        if not data:
            return None

        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return None


def load_tracks_from_directory(directory: Path) -> list[Track]:
    """扫描目录下的音频文件，并匹配同目录 lyrics 子文件夹中的歌词。"""
    lyrics_index = build_lyrics_index(directory / "lyrics")
    tracks: list[Track] = []
    for f in sorted(directory.iterdir()):
        if not (f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS):
            continue
        info = read_audio_info(f)
        tracks.append(
            Track(
                path=f,
                artist=get_track_artist(f)
                or info.get("artist", ""),
                duration=info.get("duration", 0.0),
                lyrics_path=match_lyrics_path(lyrics_index, f.stem),
                cover_src=extract_cover_src(f),
                album=info.get("album", ""),
                file_size=f.stat().st_size,
                sample_rate=info.get("sample_rate", 0),
                bitrate=info.get("bitrate", 0),
                channels=info.get("channels", 0),
            )
        )
    return tracks


def create_track(path: Path) -> Track | None:
    """从单个音频文件创建 Track，格式不支持时返回 None。"""
    resolved = path.resolve()
    if not resolved.is_file() or resolved.suffix.lower() not in SUPPORTED_FORMATS:
        return None
    lyrics_index = build_lyrics_index(resolved.parent / "lyrics")
    info = read_audio_info(resolved)
    return Track(
        path=resolved,
        artist=info.get("artist", ""),
        duration=info.get("duration", 0.0),
        lyrics_path=match_lyrics_path(lyrics_index, resolved.stem),
        cover_src=extract_cover_src(resolved),
        album=info.get("album", ""),
        file_size=resolved.stat().st_size,
        sample_rate=info.get("sample_rate", 0),
        bitrate=info.get("bitrate", 0),
        channels=info.get("channels", 0),
    )


@dataclass(frozen=True)
class StartupLoad:
    """启动时加载的曲目列表与播放目标。"""

    tracks: list[Track]
    play_index: int
    autoplay: bool


def resolve_startup_load(path: Path) -> StartupLoad | None:
    """根据启动路径解析曲目：文件则加载同目录并播放该曲，目录则仅导入。"""
    resolved = path.expanduser().resolve()
    if resolved.is_dir():
        tracks = load_tracks_from_directory(resolved)
        if not tracks:
            return None
        return StartupLoad(tracks, 0, False)

    track = create_track(resolved)
    if track is None:
        return None

    tracks = load_tracks_from_directory(resolved.parent)
    if not tracks:
        return StartupLoad([track], 0, True)

    play_index = next(
        (i for i, item in enumerate(tracks) if item.path.resolve() == track.path.resolve()),
        -1,
    )
    if play_index < 0:
        tracks = sorted([*tracks, track], key=lambda item: item.path.name.lower())
        play_index = next(
            i for i, item in enumerate(tracks) if item.path.resolve() == track.path.resolve()
        )
    return StartupLoad(tracks, play_index, True)


# ── 播放器 ── #


class Player:
    """基于 flet-audio 的播放器。

    Windows 上 ``audio.play()`` 会超时，因此切歌时通过重建
    ``Audio`` 控件（autoplay=True）触发播放；
    pause / resume / seek 直接 await 即可。
    """

    def __init__(self, callbacks: PlayerCallbacks, page: ft.Page) -> None:
        self._cb = callbacks
        self._page = page
        self.tracks: list[Track] = []
        self.current: int = -1
        self.mode: str = MODE_SEQUENCE
        self._playing = False
        self._volume = 0.7
        self._audio: fa.Audio | None = None

    # —— Audio 控件生命周期 —— #

    def _new_audio(self, src: str) -> fa.Audio:
        return fa.Audio(
            src=src,
            autoplay=True,
            volume=self._volume,
            on_state_change=self._on_state,
            on_duration_change=self._on_duration,
            on_position_change=self._on_position,
        )

    def _remount(self, audio: fa.Audio) -> None:
        """替换 page.services 中的 Audio 控件。"""
        if self._audio is not None:
            try:
                self._page.services.remove(self._audio)
            except ValueError:
                pass
        self._audio = audio
        self._page.services.append(audio)
        self._page.update()

    # —— flet-audio 事件回调 —— #

    def _on_position(self, e) -> None:
        self._cb.on_position(e.position / 1000.0)

    def _on_duration(self, e) -> None:
        dur = e.duration
        seconds = dur.in_seconds if hasattr(dur, "in_seconds") else 0.0
        self._cb.on_duration(float(seconds))

    def _on_state(self, e) -> None:
        state = e.state
        if state == fa.AudioState.PLAYING:
            self._playing = True
            self._cb.on_play_state(True)
        elif state == fa.AudioState.PAUSED:
            self._playing = False
            self._cb.on_play_state(False)
        elif state == fa.AudioState.COMPLETED:
            self._playing = False
            self._cb.on_play_state(False)
            asyncio.create_task(self.next(auto=True))

    # —— 曲目索引计算 —— #

    def set_tracks(self, tracks: list[Track]) -> None:
        self.tracks = tracks
        self.current = -1 if not tracks else 0

    def _random_index(self) -> int:
        """随机选一首，尽量避开当前曲目。"""
        if len(self.tracks) <= 1:
            return 0
        if self.current < 0:
            return random.randrange(len(self.tracks))
        idx = random.randrange(len(self.tracks) - 1)
        return idx if idx < self.current else idx + 1

    def _next_index(self, auto: bool) -> int | None:
        """计算下一首曲目索引。手动切换同样遵循播放模式。"""
        if not self.tracks:
            return None
        if self.mode == MODE_LOOP_ONE:
            return self.current
        if self.mode == MODE_SHUFFLE:
            return self._random_index()
        # 顺序播放：手动始终循环，自动播完列表停止
        if not auto:
            return (self.current + 1) % len(self.tracks) if self.current >= 0 else 0
        nxt = self.current + 1
        return nxt if nxt < len(self.tracks) else None

    def _prev_index(self) -> int | None:
        """计算上一首曲目索引，同样遵循播放模式。"""
        if not self.tracks:
            return None
        if self.mode == MODE_LOOP_ONE:
            return self.current
        if self.mode == MODE_SHUFFLE:
            return self._random_index()
        idx = self.current if self.current >= 0 else 0
        return (idx - 1) % len(self.tracks)

    # —— 播放控制 —— #

    async def play_at(self, index: int) -> None:
        if not (0 <= index < len(self.tracks)):
            return
        self.current = index
        track = self.tracks[index]
        self._cb.on_duration(get_track_duration(track.path))
        self._cb.on_position(0.0)
        self._remount(self._new_audio(str(track.path)))
        self._cb.on_track_change(index)

    async def toggle(self) -> None:
        if self.current < 0:
            if self.tracks:
                await self.play_at(0)
            return
        if self._audio is None:
            return
        if self._playing:
            await self._audio.pause()
        else:
            await self._audio.resume()

    async def next(self, auto: bool = False) -> None:
        target = self._next_index(auto)
        if target is None:
            self._cb.on_play_state(False)
            return
        await self.play_at(target)

    async def prev(self) -> None:
        target = self._prev_index()
        if target is None:
            return
        await self.play_at(target)

    async def seek(self, seconds: float) -> None:
        if self._audio is not None:
            try:
                await self._audio.seek(ft.Duration(seconds=seconds))
            except Exception:
                pass

    def set_volume(self, value: float) -> None:
        self._volume = max(0.0, min(1.0, value))
        if self._audio is not None:
            self._audio.volume = self._volume
            self._audio.update()

    def cycle_mode(self) -> str:
        self.mode = MODE_ORDER[(MODE_ORDER.index(self.mode) + 1) % len(MODE_ORDER)]
        return self.mode

    def shutdown(self) -> None:
        if self._audio is not None:
            try:
                self._page.services.remove(self._audio)
                self._page.update()
            except Exception:
                pass
            self._audio = None
