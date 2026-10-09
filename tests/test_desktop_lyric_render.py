"""桌面歌词渲染层（``desktop_lyric_render``）的版式回归。

这一层是纯函数、不碰 Win32，所以能在任何平台上跑；窗口那一侧的行为用
``.workbuddy/probe`` 里的探针在真机上验证。
"""

from __future__ import annotations

from PIL import Image

from cs_music_player.desktop_lyric_render import (
    BUTTON_SPECS,
    MIN_WIDTH,
    PAD_X,
    PAD_Y,
    TOOLBAR_GAP,
    TOOLBAR_HEIGHT,
    _elide,
    load_font,
    render_frame,
    to_premultiplied_bgra,
    toolbar_width,
)

LINE = "越过山丘 虽然已白了头"
NEXT_LINE = "喋喋不休 时不我予的哀愁"

CURRENT, NEXT, SIZE = LINE, NEXT_LINE, 20.0


def frame(**kwargs):
    params = {
        "text": CURRENT,
        "next_text": NEXT,
        "font_size": SIZE,
        "scale": 1.0,
    }
    params.update(kwargs)
    return render_frame(**params)


# ── 画布 ── #


def test_frame_size_matches_image() -> None:
    """返回的宽高就是位图尺寸——窗口侧直接拿它 SetWindowPos。"""
    result = frame()
    assert (result.width, result.height) == result.image.size
    assert result.image.mode == "RGBA"


def test_canvas_width_is_content_plus_padding() -> None:
    """窄歌词走「最小宽度」兜底，保证工具条放得下。"""
    narrow = frame(text="啊", next_text=None)
    assert narrow.width >= round(MIN_WIDTH + PAD_X * 2) - 1
    assert narrow.width <= round(toolbar_width(1.0) + PAD_X * 2) + 1


def test_longer_text_makes_wider_canvas() -> None:
    short = frame(text=LINE, next_text=None)
    long = frame(text=LINE * 3, next_text=None)
    assert long.width > short.width


def test_bigger_font_makes_taller_canvas() -> None:
    small = frame(font_size=16.0)
    large = frame(font_size=40.0)
    assert large.height > small.height
    assert large.width > small.width


# ── 工具条 ── #


def test_toolbar_grows_downward_without_moving_text() -> None:
    """悬停时工具条**向下**生长：文字一行都不许动。

    文字不动的判据取「墨迹包围盒 + 墨迹面积」——用 alpha>128 把字形本体从柔和
    投影里切出来。逐像素全等做不到：字形图层是可变的画布高，超采样缩回 1× 时
    边缘会有 ±2 的取整差（肉眼不可见），但任何真正的位移都会立刻改变包围盒。
    """
    for size in (16.0, 20.0, 30.0, 56.0):
        idle = frame(font_size=size, hovered=False)
        hover = frame(font_size=size, hovered=True)

        assert hover.height > idle.height
        assert hover.height - idle.height == round(TOOLBAR_GAP + TOOLBAR_HEIGHT)
        assert hover.width == idle.width

        keep = idle.height - round(PAD_Y)
        box = (0, 0, idle.width, keep)
        ink = [
            item.image.crop(box).getchannel("A").point(lambda v: 255 if v > 128 else 0)
            for item in (idle, hover)
        ]
        assert ink[0].getbbox() == ink[1].getbbox()
        # 面积只允许 1% 的浮动（阈值附近的取整抖动），位移会直接改变包围盒。
        area = ink[0].histogram()[255]
        assert abs(area - ink[1].histogram()[255]) <= max(8, area // 100)


def test_hint_replaces_toolbar() -> None:
    """锁定提示优先于工具条：锁定后按钮点不到，只留说明气泡。"""
    hint = frame(hovered=True, hint="歌词已锁定 · 在播放器主界面可解锁")
    assert hint.hint is not None
    assert hint.buttons == {}
    assert hint.toolbar is None


def test_buttons_are_laid_out_left_to_right_inside_canvas() -> None:
    hover = frame(hovered=True)
    names = [name for name, _ in BUTTON_SPECS if name != "sep"]
    assert list(hover.buttons) == names
    assert hover.toolbar is not None

    previous_right = None
    for name in names:
        left, top, right, bottom = hover.buttons[name]
        assert 0 <= left < right <= hover.width
        assert hover.toolbar[0] <= left and right <= hover.toolbar[2]
        assert 0 <= top < bottom <= hover.height
        if previous_right is not None:
            assert left >= previous_right
        previous_right = right


def test_toolbar_is_centered() -> None:
    hover = frame(hovered=True)
    left, _, right, _ = hover.toolbar
    assert abs((left + right) / 2 - hover.width / 2) <= 1


def test_playing_only_changes_the_toggle_glyph() -> None:
    """播放/暂停只换图标：几何不能变，否则按钮会在点击瞬间移位。"""
    playing = frame(hovered=True, playing=True)
    paused = frame(hovered=True, playing=False)
    assert playing.buttons == paused.buttons
    assert (playing.width, playing.height) == (paused.width, paused.height)
    assert playing.image.tobytes() != paused.image.tobytes()


# ── 超长行省略 ── #


def test_elide_keeps_text_that_fits() -> None:
    font = load_font(20)
    assert _elide("短句", font, 1000) == "短句"


def test_elide_clips_to_limit_with_ellipsis() -> None:
    font = load_font(20)
    text = "This ain't a song for the broken-hearted, no silent prayer"
    limit = 120.0
    clipped = _elide(text, font, limit)
    assert clipped.endswith("…")
    assert len(clipped) < len(text)
    assert font.getlength(clipped) <= limit


def test_max_width_caps_canvas_and_elides() -> None:
    """超长行 + 宽度上限：画布不超过上限，且确实换成了省略号。"""
    long_text = LINE * 6
    uncapped = frame(text=long_text, next_text=None)
    capped = frame(text=long_text, next_text=None, max_width=400.0)

    assert uncapped.width > 400
    assert capped.width <= 400
    assert capped.image.crop((0, 0, capped.width, capped.height)).tobytes() != (
        uncapped.image.crop((0, 0, capped.width, capped.height)).tobytes()
    )


def test_max_width_does_not_shrink_short_text() -> None:
    plain = frame(hovered=True)
    capped = frame(hovered=True, max_width=4000.0)
    assert (plain.width, plain.height) == (capped.width, capped.height)


# ── 位图交付 ── #


def test_premultiplied_bgra_is_blue_green_red_alpha() -> None:
    """分层窗口要预乘 BGRA；不预乘半透明边缘会出白边。"""
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 128))
    raw = to_premultiplied_bgra(image)
    assert len(raw) == 2 * 2 * 4
    assert tuple(raw[:4]) == (0, 0, 128, 128)


def test_premultiplied_bgra_zeroes_fully_transparent_pixels() -> None:
    """全透明像素必须是全 0，否则 UpdateLayeredWindow 会画出一层淡色底。"""
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    assert set(to_premultiplied_bgra(image)) == {0}
