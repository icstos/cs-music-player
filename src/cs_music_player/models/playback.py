"""播放域的枚举与状态快照。"""

from __future__ import annotations

from enum import StrEnum


class PlayMode(StrEnum):
    """播放模式。

    取值即界面文案（也是持久化后用于对比的稳定标识），因此历史上以
    ``MODE_SEQUENCE`` 等字符串常量使用的地方可以无缝替换。
    """

    SEQUENCE = "顺序播放"
    LOOP_ONE = "单曲循环"
    SHUFFLE = "随机播放"


#: 兼容旧名字。
MODE_SEQUENCE: PlayMode = PlayMode.SEQUENCE
MODE_LOOP_ONE: PlayMode = PlayMode.LOOP_ONE
MODE_SHUFFLE: PlayMode = PlayMode.SHUFFLE

#: 循环切换顺序。
MODE_ORDER: tuple[PlayMode, ...] = (
    PlayMode.SEQUENCE,
    PlayMode.LOOP_ONE,
    PlayMode.SHUFFLE,
)


