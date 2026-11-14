"""标签乱码修复：中文 MP3 常见的「GBK 字节被标成 LATIN1」。

这类乱码只该修「看起来就是乱码」的串，绝不能误伤正常的西文标签——
歌手叫 ``Björk`` 却被改成汉字，比留着乱码还难受。
"""

from __future__ import annotations

import pytest

from cs_music_player.infra.metadata import repair_mojibake


@pytest.mark.parametrize(
    "broken, fixed",
    [
        ("°àµÃÈð", "班得瑞"),
        ("Ñ©Ö®ÃÎ£¨Snowdreams£©", "雪之梦（Snowdreams）"),
        ("Rhine riverÀ³ÒðºÓ²¨Ó°", "Rhine river莱茵河波影"),
    ],
)
def test_gbk_bytes_misread_as_latin1_are_repaired(broken: str, fixed: str) -> None:
    assert repair_mojibake(broken) == fixed


def test_utf8_bytes_misread_as_latin1_are_repaired() -> None:
    assert repair_mojibake("Ã©") == "é"


@pytest.mark.parametrize(
    "text",
    [
        "Björk",
        "Mötley Crüe",
        "Café",
        "AC/DC",
        "雪之梦",
        "Bandari - Snowdreams",
        "",
    ],
)
def test_legitimate_text_is_left_alone(text: str) -> None:
    assert repair_mojibake(text) == text


def test_single_accented_letter_is_not_treated_as_mojibake() -> None:
    """单个变音字母是正常西文（``ö``），不能被两两拼成汉字。"""
    assert repair_mojibake("Björk") == "Björk"
