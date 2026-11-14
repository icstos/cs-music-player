"""配色主题：种子唯一、显示名唯一、明暗偏好只给「名字自带倾向」的那两套。

配色**不再是**一套手写色值表。cs-ui 的色板引擎从「一个品牌色种子」解算出
46 个 Material 3 角色（明暗各一套），主色的明度按对比度求解，中性表面掺一点
同色相。于是这里能守住的契约只有三条 —— 也正好是「换配色」这件事真正的要求：

1. 每套配色都有种子，且 10 个种子互不相同（否则「换配色」等于没换）；
2. 每套配色都有显示名，名字也互不相同（面板上两行同名等于只有 9 套）；
3. 种子是合法的 ``#rrggbb``（引擎会兜底，但写错一位就会悄悄退回另一个色相）。

对比度不在这里断言：它由 ``ui.core.palette`` 保证，并由 cs-ui 自己的
``_palette_logic.py`` 用 8 个种子 × 2 种模式逐项验证（正文 ≥4.5、主色实底上的
文字 ≥4.5）。在本项目重抄一遍既是重复，也会在 cs-ui 调整算法时误报。
"""

from __future__ import annotations

import re

import pytest

from cs_music_player.models import (
    COLOR_THEMES,
    DEFAULT_COLOR_THEME,
    THEME_NAMES,
    THEME_PREFERRED_MODE,
    THEME_SEEDS,
    ColorTheme,
    ThemeMode,
    name_of,
    seed_of,
)

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_every_theme_has_a_seed_name_and_order() -> None:
    """枚举、种子表、名字表一一对应，且顺序一致（面板展示顺序即枚举顺序）。"""
    assert [theme for theme in ColorTheme] == list(COLOR_THEMES)
    assert set(THEME_SEEDS) == set(ColorTheme)
    assert set(THEME_NAMES) == set(ColorTheme)
    assert len(COLOR_THEMES) == 10


def test_seeds_are_well_formed_hex() -> None:
    for theme in COLOR_THEMES:
        assert HEX.match(seed_of(theme)), f"{theme.value} -> {seed_of(theme)}"


def test_seeds_are_pairwise_distinct() -> None:
    """10 个配色必须是 10 个不同的主色。"""
    seeds = [seed_of(theme).lower() for theme in COLOR_THEMES]
    assert len(set(seeds)) == len(seeds)


def test_names_are_pairwise_distinct_and_readable() -> None:
    names = [name_of(theme) for theme in COLOR_THEMES]
    assert len(set(names)) == len(names)
    assert all(name.strip() for name in names)


def test_unknown_theme_falls_back_to_default() -> None:
    """未知标识（例如回滚到旧版本后读到新版本存下的值）不应炸。"""
    unknown = "nope"  # type: ignore[assignment]
    assert seed_of(unknown) == seed_of(DEFAULT_COLOR_THEME)
    assert name_of(unknown) == name_of(DEFAULT_COLOR_THEME)


def test_only_self_explanatory_themes_carry_a_preferred_mode() -> None:
    """只有「极简白 / 暗夜黑」这类名字自带明暗倾向的配色才改写外观。"""
    assert THEME_PREFERRED_MODE == {
        ColorTheme.MINIMAL_WHITE: ThemeMode.LIGHT,
        ColorTheme.MIDNIGHT: ThemeMode.DARK,
    }


@pytest.mark.parametrize("theme", COLOR_THEMES)
def test_seeds_survive_the_csui_palette_engine(theme: ColorTheme) -> None:
    """种子进引擎后，明暗两套主色都真的不一样 —— 否则「切明暗」看不出变化。"""
    from ui.core.palette import build_scheme

    light = build_scheme(seed_of(theme), "light")
    dark = build_scheme(seed_of(theme), "dark")
    assert light["primary"] != dark["primary"]
    # 主色与自己的容器色必须不同档，否则选中行与主按钮糊成一块
    assert light["primary"] != light["primary_container"]
