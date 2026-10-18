"""配色系统：令牌完整性、可读性与推导规则。

这些断言是「加一个配色不会把界面搞瞎」的护栏：任何新配色只要对比度不够，
这里就会红。
"""

from __future__ import annotations

import re

import pytest

from cs_music_player.models import COLOR_THEMES, DEFAULT_COLOR_THEME, ColorTheme
from cs_music_player.view.colors import (
    PALETTE_KEYS,
    THEME_SPECS,
    build_palette,
    contrast_ratio,
    ensure_contrast,
    mix,
    readable_on,
    spec_of,
)

HEX = re.compile(r"^#[0-9a-f]{6}$")

#: 正文与小字的可读性下限（WCAG AA 正文 4.5，大字号/图标 3.0）。
TEXT_MIN = 4.5
ACCENT_MIN = 3.0


def _tokens(theme: ColorTheme, dark: bool) -> dict[str, str]:
    return build_palette(theme, dark=dark)


# ── 结构 ── #


def test_every_color_theme_is_declared_and_ordered() -> None:
    """配色枚举与声明表一一对应，且顺序一致（面板展示顺序即枚举顺序）。"""
    assert [theme for theme in ColorTheme] == list(COLOR_THEMES)
    assert set(THEME_SPECS) == set(ColorTheme)
    assert len(COLOR_THEMES) == 10


def test_palette_tokens_are_complete_and_well_formed() -> None:
    for theme in COLOR_THEMES:
        for dark in (False, True):
            tokens = _tokens(theme, dark)
            assert tuple(tokens) == PALETTE_KEYS
            for name, value in tokens.items():
                assert HEX.match(value), f"{theme.value}/{dark}/{name}={value}"


def test_unknown_theme_falls_back_to_default_spec() -> None:
    assert spec_of(DEFAULT_COLOR_THEME).label == "商务蓝"
    # 未知标识（例如回滚到旧版本后读到新版本存下的值）不应炸
    assert spec_of("nope") is spec_of(DEFAULT_COLOR_THEME)  # type: ignore[arg-type]
    assert build_palette("nope", dark=False) == build_palette(  # type: ignore[arg-type]
        DEFAULT_COLOR_THEME, dark=False
    )


# ── 可读性 ── #


@pytest.mark.parametrize("theme", COLOR_THEMES)
@pytest.mark.parametrize("dark", [False, True])
def test_body_text_is_readable_on_background(theme: ColorTheme, dark: bool) -> None:
    tokens = _tokens(theme, dark)
    assert contrast_ratio(tokens["TEXT_MAIN"], tokens["BG"]) >= TEXT_MIN
    assert contrast_ratio(tokens["TEXT_MAIN"], tokens["SURFACE"]) >= TEXT_MIN


@pytest.mark.parametrize("theme", COLOR_THEMES)
@pytest.mark.parametrize("dark", [False, True])
def test_primary_and_accent_are_usable_as_text(theme: ColorTheme, dark: bool) -> None:
    """主色/强调色也会当小字用（序号、图标、开关标注），不能糊在底上。"""
    tokens = _tokens(theme, dark)
    assert contrast_ratio(tokens["PRIMARY"], tokens["BG"]) >= ACCENT_MIN
    assert contrast_ratio(tokens["ACCENT"], tokens["BG"]) >= ACCENT_MIN


@pytest.mark.parametrize("theme", COLOR_THEMES)
@pytest.mark.parametrize("dark", [False, True])
def test_on_primary_text_contrasts_with_primary(theme: ColorTheme, dark: bool) -> None:
    tokens = _tokens(theme, dark)
    assert contrast_ratio(tokens["ON_PRIMARY"], tokens["PRIMARY"]) >= TEXT_MIN
    assert contrast_ratio(tokens["ON_ACCENT"], tokens["ACCENT"]) >= ACCENT_MIN


@pytest.mark.parametrize("theme", COLOR_THEMES)
@pytest.mark.parametrize("dark", [False, True])
def test_layers_are_distinguishable(theme: ColorTheme, dark: bool) -> None:
    """背景 / 卡片 / 柔和面 / 描边四层必须各差一档，否则界面会糊成一片。"""
    tokens = _tokens(theme, dark)
    layers = [tokens["BG"], tokens["SURFACE"], tokens["SURFACE_SOFT"], tokens["BORDER"]]
    assert len(set(layers)) == len(layers)
    for first, second in zip(layers, layers[1:]):
        assert first != second


@pytest.mark.parametrize("theme", COLOR_THEMES)
def test_tooltip_card_stays_dark_on_light_and_light_on_dark(
    theme: ColorTheme,
) -> None:
    """悬浮卡是「深色质感卡片」：浅色主题下必须比背景暗并保持可读，
    深色主题下要比背景亮一档（否则跟背景融在一起）。"""
    light = _tokens(theme, dark=False)
    dark = _tokens(theme, dark=True)
    assert contrast_ratio(light["TOOLTIP_TEXT"], light["TOOLTIP_BG"]) >= TEXT_MIN
    assert contrast_ratio(dark["TOOLTIP_TEXT"], dark["TOOLTIP_BG"]) >= TEXT_MIN
    assert contrast_ratio(light["TOOLTIP_BG"], light["BG"]) >= 4.0
    assert contrast_ratio(dark["TOOLTIP_BG"], dark["BG"]) >= 1.05


def test_light_and_dark_variants_are_actually_different() -> None:
    for theme in COLOR_THEMES:
        light = _tokens(theme, dark=False)
        dark = _tokens(theme, dark=True)
        assert contrast_ratio(light["BG"], dark["BG"]) > 10
        assert light["PRIMARY"] != dark["PRIMARY"]


def test_every_theme_has_its_own_primary() -> None:
    """10 个配色必须是 10 个不同的主色，否则「换配色」等于没换。"""
    primaries = {
        _tokens(theme, dark=False)["PRIMARY"] for theme in COLOR_THEMES
    }
    assert len(primaries) == len(COLOR_THEMES)


# ── 颜色运算 ── #


def test_mix_endpoints_and_midpoint() -> None:
    assert mix("#000000", "#ffffff", 0.0) == "#000000"
    assert mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
    # 越界的比例按夹紧处理，不会产生非法颜色
    assert mix("#000000", "#ffffff", -1) == "#000000"
    assert mix("#000000", "#ffffff", 2) == "#ffffff"


def test_contrast_ratio_is_symmetric_and_bounded() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21, abs=0.01)
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21, abs=0.01)
    assert contrast_ratio("#2563eb", "#2563eb") == pytest.approx(1, abs=0.001)


def test_readable_on_picks_the_higher_contrast_ink() -> None:
    assert readable_on("#ffffff") == "#10151f"
    assert readable_on("#111827") == "#ffffff"


def test_ensure_contrast_darkens_until_readable() -> None:
    light_color = "#fde68a"  # 浅黄在白底上几乎看不见
    fixed = ensure_contrast(light_color, "#ffffff")
    assert contrast_ratio(fixed, "#ffffff") >= 4.0
    # 已经够读的颜色不该被动
    assert ensure_contrast("#111827", "#ffffff") == "#111827"
