"""CS Music Player — 基于 Flet 的本地音乐播放器。

对外仍然提供 ``Player`` / ``Track`` / ``MODE_*`` 这些常用名字，但**不再**在
导入包时就加载它们：``.audio_player`` 会连带拉起 flet_audio / miniaudio /
mutagen（≈43ms），而启动路径上 ``main.py`` 需要的只是 ``.startup`` 这个
纯标准库小模块。于是改用 PEP 562 的模块级 ``__getattr__`` 惰性转出——
谁用到谁才加载，`from cs_music_player import Player` 这类写法照旧可用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 仅供类型检查器与 IDE 解析，运行期不执行
    from .audio_player import (
        Player,
        PlayerCallbacks,
        Track,
        load_tracks_from_directory,
    )
    from .constants import (
        MODE_LOOP_ONE,
        MODE_SEQUENCE,
        MODE_SHUFFLE,
        SUPPORTED_FORMATS,
    )

__all__ = [
    "Player",
    "PlayerCallbacks",
    "Track",
    "load_tracks_from_directory",
    "MODE_SEQUENCE",
    "MODE_LOOP_ONE",
    "MODE_SHUFFLE",
    "SUPPORTED_FORMATS",
]

#: 名字 -> 定义它的子模块（相对于本包）。
_LAZY_EXPORTS = {
    "Player": "audio_player",
    "PlayerCallbacks": "audio_player",
    "Track": "audio_player",
    "load_tracks_from_directory": "audio_player",
    "MODE_SEQUENCE": "constants",
    "MODE_LOOP_ONE": "constants",
    "MODE_SHUFFLE": "constants",
    "SUPPORTED_FORMATS": "constants",
}


def __getattr__(name: str) -> Any:
    """首次访问时才导入对应子模块，并把结果缓存进本模块命名空间。"""

    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
