"""基础设施层：封装底层技术实现，对外暴露抽象接口。

本层向上只交出 :mod:`cs_music_player.infra.ports` 里的 ``Protocol``，以及
具体的适配器实现；服务层只依赖前者。

为了让启动路径保持轻量，本包的 ``__init__`` **不导入任何子模块**——flet /
mutagen / Pillow / ctypes 都由用到的那一层按需导入（PEP 562 惰性转出）。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AudioEngineObserver",
    "AudioEnginePort",
    "DesktopLyricPort",
    "DirectoryPickerPort",
    "Dispatcher",
    "LyricsProviderPort",
    "LyricsRepositoryPort",
    "MetadataPort",
    "PreferencesPort",
]

#: 名字 → 定义它的子模块（相对于本包）。
_LAZY_EXPORTS = {
    "AudioEngineObserver": "ports",
    "AudioEnginePort": "ports",
    "DesktopLyricPort": "ports",
    "DirectoryPickerPort": "ports",
    "Dispatcher": "ports",
    "LyricsProviderPort": "ports",
    "LyricsRepositoryPort": "ports",
    "MetadataPort": "ports",
    "PreferencesPort": "ports",
}


def __getattr__(name: str) -> Any:
    """首次访问时才导入对应子模块（``ports`` 本身很轻）。"""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
