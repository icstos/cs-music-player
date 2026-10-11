"""CS Music Player — 基于 Flet 的本地音乐播放器。

代码按**五层单向依赖**组织：

```
view ──▶ viewmodel ──▶ service ──▶ infra
   ╲         │            │          │
    ╲        ▼            ▼          ▼
     ╲────────────── models ─────────┘
```

- :mod:`cs_music_player.models` —— 数据结构、枚举、常量（无业务逻辑，所有层可依赖）
- :mod:`cs_music_player.infra` —— 底层技术实现与其抽象接口（``infra.ports``）
- :mod:`cs_music_player.service` —— 业务流程编排，只依赖抽象接口
- :mod:`cs_music_player.viewmodel` —— UI 状态与动作（纯 Python，零 Flet 依赖）
- :mod:`cs_music_player.view` —— 声明式 Flet 界面（无业务逻辑）

:mod:`cs_music_player.bootstrap` 是组装根；:mod:`main` 是程序入口。

为了让启动路径保持轻量，本包**不在导入期加载任何子模块**：常用名字改用
PEP 562 的模块级 ``__getattr__`` 惰性转出，``from cs_music_player import Track``
这类写法照旧可用，但 ``import cs_music_player`` 本身几乎不花时间。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 仅供类型检查器与 IDE 解析，运行期不执行
    from .models import (
        MODE_LOOP_ONE,
        MODE_SEQUENCE,
        MODE_SHUFFLE,
        SUPPORTED_FORMATS,
        DesktopLyricConfig,
        LyricLine,
        PlayMode,
        ThemeMode,
        Track,
    )

__all__ = [
    "MODE_LOOP_ONE",
    "MODE_SEQUENCE",
    "MODE_SHUFFLE",
    "SUPPORTED_FORMATS",
    "DesktopLyricConfig",
    "LyricLine",
    "PlayMode",
    "ThemeMode",
    "Track",
]

#: 名字 -> 定义它的子模块（相对于本包）。
_LAZY_EXPORTS = {
    "Track": "models",
    "LyricLine": "models",
    "PlayMode": "models",
    "ThemeMode": "models",
    "DesktopLyricConfig": "models",
    "SUPPORTED_FORMATS": "models",
    "MODE_SEQUENCE": "models",
    "MODE_LOOP_ONE": "models",
    "MODE_SHUFFLE": "models",
}


def __getattr__(name: str) -> Any:
    """首次访问时才导入对应子模块，并把结果缓存进本模块命名空间。"""

    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
