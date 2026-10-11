"""极简观察者基类：视图模型用它把状态变化广播给视图。

**零第三方依赖**（连 Flet 都不导入），因此视图模型可以在没有 UI 的环境里
被完整单测；视图层负责把这里的通知桥接成 Flet 的重渲染。
"""

from __future__ import annotations

from collections.abc import Callable

__all__ = ["ChangeListener", "ObservableModel"]

#: 状态变化监听器：无参数、无返回值。
ChangeListener = Callable[[], None]


class ObservableModel:
    """可被订阅的状态容器。

    子类在改完一组字段后显式调用 :meth:`notify`——一次逻辑更新只广播一次，
    不会被中间态打断。
    """

    def __init__(self) -> None:
        self._listeners: list[ChangeListener] = []

    def subscribe(self, listener: ChangeListener) -> Callable[[], None]:
        """注册监听器，返回取消订阅的函数。"""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def notify(self) -> None:
        """广播一次状态变化。"""
        for listener in tuple(self._listeners):
            listener()

    @property
    def listener_count(self) -> int:
        """当前监听器数量（便于测试与诊断）。"""
        return len(self._listeners)
