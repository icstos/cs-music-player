"""音频元数据读取（mutagen）。

对外只暴露 :class:`MutagenMetadataReader`，它实现
:class:`cs_music_player.infra.ports.MetadataPort`；上层永远看不到 mutagen。
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from ..models import AudioMetadata, TagText

__all__ = ["MutagenMetadataReader"]


def _open_audio(path: Path) -> tuple[Any, Any]:
    """打开音频文件并返回 ``(audio, tags)``；失败返回 ``(None, None)``。"""
    try:
        from mutagen import File

        audio = File(str(path))
    except Exception:
        return None, None
    tags = getattr(audio, "tags", None) if audio is not None else None
    return audio, tags


def _tag_value(tags: Any, *keys: str) -> str:
    """从标签对象中按候选键读取文本值，优先级由参数顺序决定。"""
    if tags is None:
        return ""
    for key in keys:
        value = tags.get(key)
        if value is None:
            continue
        if hasattr(value, "text"):
            raw = value.text
            if isinstance(raw, (list, tuple)):
                items = [str(i) for i in raw]
            else:
                items = [str(raw)] if raw else []
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


def _first_tag_value(tags: Any, *keys: str) -> str:
    """按候选键取**第一个**非空的标签文本（多值标签只取首值）。

    与 :func:`_tag_value` 的区别：后者把多值标签用 ``" / "`` 连起来，是给
    界面展示用的；在线歌词检索要的是标签原值。
    """
    if not tags:
        return ""
    for key in keys:
        value = tags.get(key)
        if value is None:
            continue
        raw = value.text if hasattr(value, "text") else value
        parts = raw if isinstance(raw, list) else [raw]
        for part in parts:
            text = str(part).strip()
            if text:
                return text
    return ""


_TITLE_KEYS = ("TIT2", "title", "\xa9nam", "TITLE")
_QUERY_ARTIST_KEYS = ("TPE1", "artist", "\xa9ART", "ARTIST")
_QUERY_ALBUM_KEYS = ("TALB", "album", "\xa9alb", "ALBUM")


def read_tag_text(path: Path) -> TagText:
    """读取标签里的标题 / 歌手 / 专辑原文；读取失败时返回空值。"""
    try:
        audio, tags = _open_audio(path)
        if audio is None or tags is None:
            return TagText()
        return TagText(
            title=_first_tag_value(tags, *_TITLE_KEYS),
            artist=_first_tag_value(tags, *_QUERY_ARTIST_KEYS),
            album=_first_tag_value(tags, *_QUERY_ALBUM_KEYS),
        )
    except Exception:
        return TagText()


_ARTIST_KEYS = (
    "artist",
    "TPE1",
    "albumartist",
    "TPE2",
    "\xa9ART",
    "performer",
)
_ALBUM_KEYS = ("album", "TALB", "\xa9alb", "ALBUM")


def read_audio_info(path: Path) -> AudioMetadata:
    """一次性读取曲目元数据：时长、歌手、专辑、采样率、码率、声道。

    读取失败时返回默认值（全 0 / 空串）而不是抛错——扫描目录时单个坏文件
    不应该拖垮整个导入流程。
    """
    audio, tags = _open_audio(path)
    info = getattr(audio, "info", None) if audio is not None else None
    data = AudioMetadata()
    if info is not None:
        try:
            if getattr(info, "length", None) is not None:
                data.duration = float(info.length)
        except Exception:
            pass
        for attr in ("sample_rate", "bitrate", "channels"):
            value = getattr(info, attr, None)
            if value:
                setattr(data, attr, int(value))
    if tags is not None:
        album = _tag_value(tags, *_ALBUM_KEYS)
        if album:
            data.album = album
        artist = _tag_value(tags, *_ARTIST_KEYS)
        if artist:
            data.artist = artist
    return data


def extract_cover_src(path: Path) -> str | None:
    """从音频内嵌标签提取封面，返回 data URI；无封面或失败时返回 ``None``。"""
    try:
        audio, _ = _open_audio(path)
        if audio is None:
            return None

        data: bytes | None = None
        mime = "image/jpeg"

        if getattr(audio, "pictures", None):
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
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return None


class MutagenMetadataReader:
    """基于 mutagen 的 :class:`MetadataPort` 实现（无状态、可复用）。"""

    def read(self, path: Path) -> AudioMetadata:
        """读取元数据；失败时返回默认值。"""
        return read_audio_info(path)

    def cover_data_uri(self, path: Path) -> str | None:
        """提取内嵌封面为 data URI；没有封面时返回 ``None``。"""
        return extract_cover_src(path)

    def read_tag_text(self, path: Path) -> TagText:
        """读取标签里的标题 / 歌手 / 专辑原文；读取失败时返回空值。"""
        return read_tag_text(path)
