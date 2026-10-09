"""桌面歌词的画面渲染：把一份歌词状态画成一张带透明通道的位图。

桌面歌词窗是一个 **Win32 分层窗口**（``WS_EX_LAYERED`` +
``UpdateLayeredWindow``），它要求每帧提供一张「每像素 alpha」的位图。用 Pillow
画这张图比用 GDI 画省事得多：能直接拿到高斯模糊做柔和投影、能直接读本地字体
文件（``assets/fonts`` 里的 AlibabaPuHuiTi），还能顺手得到每个按钮的命中矩形。

本模块**只负责画**，不碰任何 Win32，因此可以在任意平台上单测。窗口那一侧的
事情（建窗、消息循环、鼠标穿透）在 :mod:`cs_music_player.desktop_lyrics`。

版式规则（与主界面歌词面板同一套直觉，但为「悬浮在桌面上」而重新取值）：

- 当前行最大最亮，下一行小一号、暗一档——桌面歌词只需要给人「现在唱到哪、
  下一句是什么」的信息，铺满整屏反而挡住桌面。
- 文字用「柔和投影 + 细描边」而不是色块背景：这样无论桌面是深色壁纸还是白色
  文档，字都读得清，又不会糊住背后的窗口。
- 工具条只在鼠标悬停时出现，且**向下**生长：文字位置保持不动，不会因为工具条
  冒出来而上下跳。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .constants import (
    DESKTOP_LYRIC_FONT_DEFAULT as FONT_SIZE_DEFAULT,
)
from .constants import (
    DESKTOP_LYRIC_FONT_MAX as FONT_SIZE_MAX,
)
from .constants import (
    DESKTOP_LYRIC_FONT_MIN as FONT_SIZE_MIN,
)
from .constants import (
    DESKTOP_LYRIC_FONT_STEP as FONT_SIZE_STEP,
)

__all__ = [
    "FONT_SIZE_DEFAULT",
    "FONT_SIZE_MAX",
    "FONT_SIZE_MIN",
    "FONT_SIZE_STEP",
    "Frame",
    "render_frame",
    "resolve_font_path",
    "set_font_path",
    "to_premultiplied_bgra",
    "toolbar_width",
]

# ── 版式常量（逻辑像素；实际渲染时统一乘 DPI 缩放）── #

#: 下一行相对当前行的字号比例。
NEXT_LINE_SCALE = 0.70
#: 当前行与下一行之间的间距（相对基准字号）。
LINE_GAP_RATIO = 0.34

#: 画布四周留白：给投影和描边留出扩散空间。
PAD_X = 20.0
PAD_Y = 13.0

#: 工具条。
TOOLBAR_HEIGHT = 38.0
TOOLBAR_BUTTON_WIDTH = 40.0
TOOLBAR_SEP_WIDTH = 11.0
TOOLBAR_PAD = 6.0
TOOLBAR_RADIUS = 12.0
TOOLBAR_GAP = 10.0
BUTTON_RADIUS = 8.0

#: 矢量图形（圆角面板、图标）的超采样倍数：PIL 的 ImageDraw 不抗锯齿，
#: 画完缩回 1× 才平滑。
SUPERSAMPLE = 3

#: 取景框最小宽度（逻辑像素）：保证工具条在任何歌词长度下都放得下。
MIN_WIDTH = 260.0

FONT_FILE_NAME = "AlibabaPuHuiTi-3-55-Regular.otf"

#: 底部工具条的按钮排布；``"sep"`` 是纯视觉分隔符，不参与命中。
BUTTON_SPECS: tuple[tuple[str, float], ...] = (
    ("prev", TOOLBAR_BUTTON_WIDTH),
    ("toggle", TOOLBAR_BUTTON_WIDTH),
    ("next", TOOLBAR_BUTTON_WIDTH),
    ("sep", TOOLBAR_SEP_WIDTH),
    ("font_dec", TOOLBAR_BUTTON_WIDTH),
    ("font_inc", TOOLBAR_BUTTON_WIDTH),
    ("sep", TOOLBAR_SEP_WIDTH),
    ("lock", TOOLBAR_BUTTON_WIDTH),
    ("close", TOOLBAR_BUTTON_WIDTH),
)

#: 不可点击、仅作占位的分隔符名字。
_SEPARATORS = frozenset({"sep"})

CURRENT_COLOR = (255, 255, 255, 255)
NEXT_COLOR = (255, 255, 255, 148)
PLACEHOLDER_COLOR = (255, 255, 255, 120)
ICON_COLOR = (233, 239, 247, 232)
ICON_DISABLED_COLOR = (233, 239, 247, 96)
ICON_HOVER_COLOR = (255, 255, 255, 255)
BUTTON_HOVER_BG = (255, 255, 255, 38)

_font_path_override: str | None = None
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


# ── 字体 ── #


def set_font_path(path: str | Path | None) -> None:
    """显式指定字体文件（打包后资源目录与源码目录不同，需要外部告知）。"""
    global _font_path_override
    _font_path_override = str(path) if path else None
    _font_cache.clear()


def resolve_font_path() -> str | None:
    """定位歌词字体：优先显式指定，其次仓库内 ``assets/fonts``。"""
    if _font_path_override and Path(_font_path_override).is_file():
        return _font_path_override

    here = Path(__file__).resolve().parent
    candidates = (
        here.parent / "assets" / "fonts" / FONT_FILE_NAME,
        Path.cwd() / "assets" / "fonts" / FONT_FILE_NAME,
        here / "assets" / "fonts" / FONT_FILE_NAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def load_font(px: int) -> ImageFont.FreeTypeFont:
    """按物理像素取字体，结果缓存（渲染每秒可能跑好几次）。"""
    px = max(6, int(round(px)))
    path = resolve_font_path() or ""
    key = (path, px)
    font = _font_cache.get(key)
    if font is None:
        try:
            font = ImageFont.truetype(path, px) if path else ImageFont.load_default(px)
        except OSError:
            font = ImageFont.load_default(px)
        _font_cache[key] = font
    return font


def _text_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    return float(font.getlength(text))


def _text_height(font: ImageFont.FreeTypeFont) -> float:
    ascent, descent = font.getmetrics()
    return float(ascent + descent)


def _elide(text: str, font: ImageFont.FreeTypeFont, limit: float) -> str:
    """把一行文字压进 ``limit`` 像素，超出部分用「…」收尾。

    二分找「还能放下几个字」，避免逐字累积测量（``getlength`` 不便宜）。桌面歌词
    是「一行一屏」的展示，省略比撑破屏幕好。
    """
    if not text or limit <= 0 or _text_width(text, font) <= limit:
        return text
    ellipsis = "…"
    ellipsis_w = _text_width(ellipsis, font)
    if ellipsis_w > limit:
        return ""
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if _text_width(text[:mid], font) + ellipsis_w <= limit:
            low = mid
        else:
            high = mid - 1
    return text[:low].rstrip() + ellipsis


# ── 通用绘制件 ── #


def _text_layer(
    size: tuple[int, int],
    center: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill,
    stroke_width: int = 0,
    stroke_fill=None,
) -> Image.Image:
    """把一行文字画到独立图层上（居中于 ``center``），便于单独做投影。"""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        center,
        text,
        font=font,
        fill=fill,
        anchor="mm",
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    return layer


def _soft_shadow(
    layer: Image.Image, *, blur: float, alpha: int, dy: float = 0.0
) -> Image.Image:
    """用图层的 alpha 通道做一层高斯模糊阴影。

    阴影颜色恒为黑——它要解决的是「白字压在浅色桌面上看不清」，黑色投影在
    深色桌面上也只会让字更实。
    """
    mask = layer.getchannel("A").filter(ImageFilter.GaussianBlur(max(0.0, blur)))
    if alpha < 255:
        mask = mask.point(lambda value: int(value * alpha / 255))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shadow.putalpha(mask)
    if dy:
        shadow = ImageChops.offset(shadow, 0, int(round(dy)))
    return shadow


def _compose_text(
    base: Image.Image, layer: Image.Image, *, font_px: int, dy_ratio: float = 0.055
) -> Image.Image:
    """把一行文字叠到底图上：先铺一层大范围暗晕，再补一层贴边实影，最后是字。

    两层阴影是「浅色桌面上也读得清」的关键：大半径/中等透明度的一层负责把字从
    花哨壁纸里"抠"出来，小半径/高透明度的一层补足笔画边缘的对比。
    """
    halo = _soft_shadow(layer, blur=max(1.5, font_px * 0.30), alpha=200)
    tight = _soft_shadow(
        layer, blur=max(0.6, font_px * 0.07), alpha=215, dy=font_px * dy_ratio
    )
    for shadow in (halo, tight):
        base = Image.alpha_composite(base, shadow)
    return Image.alpha_composite(base, layer)


def _rounded_panel(
    size: tuple[int, int],
    box: tuple[float, float, float, float],
    *,
    radius: float,
    fill,
    outline=None,
    outline_width: int = 1,
    shadow_blur: float = 0.0,
    shadow_alpha: int = 0,
    shadow_dy: float = 0.0,
) -> Image.Image:
    """圆角面板（可选细描边与投影），画在独立图层上。

    面板先按 :data:`SUPERSAMPLE` 倍画好再缩回 1×，圆角才不会呈阶梯状；投影在
    缩放后的 alpha 上做，边缘自然是平滑的。
    """
    ss = SUPERSAMPLE
    big = Image.new("RGBA", (size[0] * ss, size[1] * ss), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle(
        tuple(value * ss for value in box),
        radius=radius * ss,
        fill=fill,
        outline=outline,
        width=max(1, int(round(outline_width * ss))),
    )
    layer = big.resize(size, Image.LANCZOS)
    if shadow_alpha <= 0 or shadow_blur <= 0:
        return layer
    return Image.alpha_composite(
        _soft_shadow(layer, blur=shadow_blur, alpha=shadow_alpha, dy=shadow_dy), layer
    )


# ── 工具条图标（纯矢量绘制，不依赖图标字体）── #


def _draw_glyph(
    draw: ImageDraw.ImageDraw, name: str, box: tuple[float, float, float, float], color
) -> None:
    """在 ``box`` 内画一个居中图标。"""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    s = min(x1 - x0, y1 - y0) * 0.30
    stroke = max(1.5, s * 0.36)

    if name == "play":
        draw.polygon(
            [(cx - s * 0.62, cy - s), (cx - s * 0.62, cy + s), (cx + s * 0.95, cy)],
            fill=color,
        )
    elif name == "pause":
        bar = s * 0.34
        for sign in (-1, 1):
            left = cx + sign * s * 0.62 - (bar if sign < 0 else 0)
            draw.rounded_rectangle(
                [left, cy - s, left + bar, cy + s], radius=bar * 0.4, fill=color
            )
    elif name in ("prev", "next"):
        bar_w = s * 0.34
        if name == "prev":
            # ⏮：左侧竖条 + 向左的三角
            draw.rounded_rectangle(
                [cx - s * 0.98, cy - s, cx - s * 0.98 + bar_w, cy + s],
                radius=bar_w * 0.4,
                fill=color,
            )
            draw.polygon(
                [(cx + s * 0.98, cy - s), (cx + s * 0.98, cy + s), (cx - s * 0.30, cy)],
                fill=color,
            )
        else:
            # ⏭：向右的三角 + 右侧竖条
            draw.polygon(
                [(cx - s * 0.98, cy - s), (cx - s * 0.98, cy + s), (cx + s * 0.30, cy)],
                fill=color,
            )
            draw.rounded_rectangle(
                [cx + s * 0.98 - bar_w, cy - s, cx + s * 0.98, cy + s],
                radius=bar_w * 0.4,
                fill=color,
            )
    elif name == "close":
        pad = s * 0.9
        width = max(2, int(round(stroke)))
        draw.line([(cx - pad, cy - pad), (cx + pad, cy + pad)], fill=color, width=width)
        draw.line([(cx - pad, cy + pad), (cx + pad, cy - pad)], fill=color, width=width)
    elif name in ("lock", "unlock"):
        total_h = s * 1.82
        body_w = s * 1.20
        body_h = s * 0.84
        top = cy - total_h / 2
        body_top = top + total_h - body_h
        draw.rounded_rectangle(
            [cx - body_w / 2, body_top, cx + body_w / 2, body_top + body_h],
            radius=body_h * 0.30,
            fill=color,
        )
        # 锁环：细半圆，半径明显小于锁体半宽，才不会糊成一团。
        shackle_r = body_w * 0.36
        arc_width = max(2, int(round(s * 0.19)))
        if name == "lock":
            draw.arc(
                [
                    cx - shackle_r,
                    body_top - shackle_r,
                    cx + shackle_r,
                    body_top + shackle_r,
                ],
                start=180,
                end=360,
                fill=color,
                width=arc_width,
            )
        else:
            # 开锁：锁环向右上方掀起，露出缺口。
            draw.arc(
                [
                    cx - shackle_r + shackle_r * 0.75,
                    body_top - shackle_r * 1.10,
                    cx + shackle_r + shackle_r * 0.75,
                    body_top + shackle_r * 0.90,
                ],
                start=185,
                end=360,
                fill=color,
                width=arc_width,
            )
    elif name in ("font_dec", "font_inc"):
        font = load_font(max(10, int(round(s * 1.95))))
        draw.text((cx - s * 0.42, cy + s * 0.12), "A", font=font, fill=color, anchor="mm")
        # 字号符号：A 右上角的小加/减号
        sign_x, sign_y = cx + s * 0.92, cy - s * 0.62
        half = s * 0.42
        bar_w = max(1.6, s * 0.20)
        draw.line(
            [(sign_x - half, sign_y), (sign_x + half, sign_y)],
            fill=color,
            width=int(round(bar_w)),
        )
        if name == "font_inc":
            draw.line(
                [(sign_x, sign_y - half), (sign_x, sign_y + half)],
                fill=color,
                width=int(round(bar_w)),
            )


def _draw_button_content(
    draw: ImageDraw.ImageDraw,
    name: str,
    box: tuple[float, float, float, float],
    *,
    color,
    playing: bool,
) -> None:
    if name == "toggle":
        _draw_glyph(draw, "pause" if playing else "play", box, color)
    elif name == "prev":
        _draw_glyph(draw, "prev", box, color)
    elif name == "next":
        _draw_glyph(draw, "next", box, color)
    else:
        _draw_glyph(draw, name, box, color)


# ── 帧 ── #


@dataclass
class Frame:
    """一帧画面：位图 + 每个按钮的命中矩形（图像坐标，物理像素）。"""

    image: Image.Image
    buttons: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    toolbar: tuple[float, float, float, float] | None = None
    hint: tuple[float, float, float, float] | None = None
    width: int = 0
    height: int = 0


def toolbar_width(scale: float = 1.0) -> float:
    """工具条的固有宽度（逻辑像素 × 缩放）。"""
    inner = sum(width for _, width in BUTTON_SPECS)
    return (inner + TOOLBAR_PAD * 2) * scale


def render_frame(
    *,
    text: str | None,
    next_text: str | None,
    font_size: float,
    scale: float = 1.0,
    hovered: bool = False,
    hover_button: str | None = None,
    playing: bool = False,
    placeholder: bool = False,
    hint: str | None = None,
    max_width: float | None = None,
) -> Frame:
    """渲染一帧。

    Args:
        text: 当前行文字；``None`` 表示没有内容。
        next_text: 下一行文字；``None`` 表示没有下一行。
        font_size: 基准字号（逻辑像素）。
        scale: DPI 缩放（物理像素 = 逻辑像素 × scale）。
        hovered: 是否悬停（决定是否显示工具条）。
        hover_button: 鼠标所在按钮名，用于高亮。
        playing: 播放中（决定按钮画「暂停」还是「播放」）。
        placeholder: 无歌词时的占位文案（灰一档、不放大）。
        hint: 底部气泡文案，优先于工具条（锁定后无法点击，只能靠它说明怎么解锁）。
        max_width: 画布宽度上限（与返回的 ``Frame.width`` 同单位）。超出时文字用
            「…」省略——悬浮窗不该宽过屏幕。
    """
    scale = max(0.5, float(scale))
    font_size = float(font_size)

    current_px = max(8, int(round(font_size * scale)))
    next_px = max(8, int(round(font_size * NEXT_LINE_SCALE * scale)))
    current_font = load_font(current_px)
    next_font = load_font(next_px)

    pad_x = PAD_X * scale
    pad_y = PAD_Y * scale
    toolbar_h = TOOLBAR_HEIGHT * scale
    toolbar_gap = TOOLBAR_GAP * scale

    # 超长行先按宽度上限省略：悬浮窗宽过屏幕就会出现「看不全、也退不回去」的
    # 死局，宁可省略。上限由窗口侧按显示器工作区算好后传进来。
    current_text = text or ""
    next_line = next_text or ""
    if max_width is not None and max_width > 0:
        text_limit = max(1.0, float(max_width) - pad_x * 2)
        current_text = _elide(current_text, current_font, text_limit)
        next_line = _elide(next_line, next_font, text_limit)

    width_current = _text_width(current_text, current_font) if current_text else 0.0
    height_current = _text_height(current_font)
    width_next = _text_width(next_line, next_font) if next_line else 0.0
    height_next = _text_height(next_font) if next_line else 0.0

    line_gap = font_size * LINE_GAP_RATIO * scale
    text_height = height_current + (line_gap + height_next if next_line else 0.0)

    toolbar_w = toolbar_width(scale)
    hint_pill = _measure_hint(hint, scale) if hint else None
    hint_w = hint_pill[0] if hint_pill else 0.0
    content_w = max(width_current, width_next, toolbar_w, hint_w, MIN_WIDTH * scale)
    if max_width is not None and max_width > 0:
        # max_width 是「画布宽度」上限，所以内容区要先扣掉左右留白。
        content_w = min(content_w, max(1.0, float(max_width) - pad_x * 2))
    win_w = int(round(content_w + pad_x * 2))
    show_bar = hovered or hint is not None
    bottom_extra = (toolbar_gap + toolbar_h) if show_bar else 0.0
    win_h = int(round(pad_y + text_height + bottom_extra + pad_y))

    image = Image.new("RGBA", (max(1, win_w), max(1, win_h)), (0, 0, 0, 0))
    center_x = win_w / 2.0

    # —— 文字 —— #
    stroke = max(1, int(round(current_px * 0.045)))
    current_layer = _text_layer(
        image.size,
        (center_x, pad_y + height_current / 2),
        current_text,
        current_font,
        PLACEHOLDER_COLOR if placeholder else CURRENT_COLOR,
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 130),
    )
    image = _compose_text(image, current_layer, font_px=current_px)

    if next_line:
        next_center_y = pad_y + height_current + line_gap + height_next / 2
        next_layer = _text_layer(
            image.size,
            (center_x, next_center_y),
            next_line,
            next_font,
            NEXT_COLOR,
            stroke_width=max(1, int(round(next_px * 0.04))),
            stroke_fill=(0, 0, 0, 105),
        )
        image = _compose_text(image, next_layer, font_px=next_px)

    frame = Frame(image=image, width=win_w, height=win_h)
    if not show_bar:
        return frame

    bar_y = pad_y + text_height + toolbar_gap
    if hint is not None:
        # —— 提示气泡 —— #
        pill_w, pill_h = hint_pill or (0.0, toolbar_h)
        pill_x = (win_w - pill_w) / 2
        panel = _rounded_panel(
            image.size,
            (pill_x, bar_y, pill_x + pill_w, bar_y + pill_h),
            radius=pill_h / 2,
            fill=(15, 23, 42, 224),
            outline=(255, 255, 255, 36),
            shadow_blur=9 * scale,
            shadow_alpha=120,
            shadow_dy=2 * scale,
        )
        frame.image = Image.alpha_composite(image, panel)
        hint_font = load_font(max(10, int(round(13 * scale))))
        label = _text_layer(
            (win_w, win_h),
            (win_w / 2.0, bar_y + pill_h / 2),
            hint,
            hint_font,
            (255, 255, 255, 226),
        )
        frame.image = Image.alpha_composite(frame.image, label)
        frame.hint = (pill_x, bar_y, pill_x + pill_w, bar_y + pill_h)
        return frame

    # —— 工具条 —— #
    toolbar_x = (win_w - toolbar_w) / 2
    toolbar_box = (
        toolbar_x,
        bar_y,
        toolbar_x + toolbar_w,
        bar_y + toolbar_h,
    )
    panel = _rounded_panel(
        image.size,
        toolbar_box,
        radius=TOOLBAR_RADIUS * scale,
        fill=(15, 23, 42, 214),
        outline=(255, 255, 255, 32),
        shadow_blur=9 * scale,
        shadow_alpha=120,
        shadow_dy=2 * scale,
    )
    image = Image.alpha_composite(image, panel)
    frame.image = image

    # 图标与悬停高亮画在独立图层上并按 SUPERSAMPLE 倍超采样后缩放：
    # PIL 的 ImageDraw 既不混合 alpha、也不抗锯齿，直接画在成品图上会得到
    # 「镂空色块 + 锯齿边」；超采样是 Pillow 里拿到平滑矢量图形的标准做法。
    ss = SUPERSAMPLE
    glyphs = Image.new("RGBA", (win_w * ss, win_h * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glyphs)

    cursor_x = toolbar_x + TOOLBAR_PAD * scale
    for name, spec_width in BUTTON_SPECS:
        box = (
            cursor_x,
            bar_y,
            cursor_x + spec_width * scale,
            bar_y + toolbar_h,
        )
        cursor_x = box[2]
        scaled = tuple(value * ss for value in box)
        if name in _SEPARATORS:
            line_x = (scaled[0] + scaled[2]) / 2
            inset = toolbar_h * ss * 0.26
            draw.line(
                [
                    (line_x, scaled[1] + inset),
                    (line_x, scaled[3] - inset),
                ],
                fill=(255, 255, 255, 52),
                width=max(1, int(round(scale * ss))),
            )
            continue
        if hover_button == name:
            draw.rounded_rectangle(
                [
                    scaled[0] + 2 * scale * ss,
                    scaled[1] + 3 * scale * ss,
                    scaled[2] - 2 * scale * ss,
                    scaled[3] - 3 * scale * ss,
                ],
                radius=BUTTON_RADIUS * scale * ss,
                fill=BUTTON_HOVER_BG,
            )
        color = ICON_HOVER_COLOR if hover_button == name else ICON_COLOR
        _draw_button_content(draw, name, scaled, color=color, playing=playing)
        frame.buttons[name] = box

    del draw
    image = Image.alpha_composite(image, glyphs.resize((win_w, win_h), Image.LANCZOS))
    frame.image = image
    frame.toolbar = toolbar_box
    return frame


def _measure_hint(hint: str, scale: float) -> tuple[float, float]:
    """提示气泡的尺寸（逻辑内容 × 缩放）。"""
    font = load_font(max(10, int(round(13 * scale))))
    width = float(font.getlength(hint)) + 30 * scale
    return width, TOOLBAR_HEIGHT * 0.86 * scale


def to_premultiplied_bgra(image: Image.Image) -> bytes:
    """转成 ``UpdateLayeredWindow`` 需要的预乘 BGRA 字节流。

    分层窗口的 ``AC_SRC_ALPHA`` 语义要求颜色分量**先乘上 alpha**；不预乘的话
    半透明边缘会出现白边。Pillow 的 ``RGBa`` 模式虽然就是预乘，但它没有到
    ``BGRA`` 的打包器，于是这里用 ``ImageChops.multiply`` 手动预乘，再把通道
    按 B、G、R 的顺序塞进 ``RGBA`` 槽位——``tobytes`` 出来的自然就是 BGRA。
    """
    red, green, blue, alpha = image.convert("RGBA").split()
    scaled = [ImageChops.multiply(channel, alpha) for channel in (blue, green, red)]
    return Image.merge("RGBA", (*scaled, alpha)).tobytes("raw", "RGBA")
