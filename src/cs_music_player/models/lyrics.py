"""歌词数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LyricLine:
    """一行歌词：``time`` 为起始秒数，纯文本歌词整段为 0。"""

    time: float
    text: str


