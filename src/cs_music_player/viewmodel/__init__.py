"""视图模型层：持有 UI 状态，连接视图与服务。

**零 Flet 依赖**——视图模型是纯 Python 类，因此可以在无界面环境下被完整
单测；视图层负责把 :meth:`ObservableModel.notify` 桥接成 Flet 的重渲染。
"""

from __future__ import annotations

from .app import AppViewModel, Toast
from .observable import ChangeListener, ObservableModel

__all__ = ["AppViewModel", "ChangeListener", "ObservableModel", "Toast"]
