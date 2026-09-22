"""临时探针：验证「正在播放的歌词行停在歌词区垂直中线」。

应用（主线程 ft.run）+ 驱动（后台线程：等窗口 → 截图 → 像素分析）同进程，
全部放在一次执行内完成；结束后杀掉 flet 客户端子进程再退出。
"""

from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time

PROBE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = r"D:/Projects/cs-music-player"
LOG = os.path.join(PROBE_DIR, "probe.log")
TITLE = "LYRIC_CENTER_PROBE"

sys.path.insert(0, PROJECT)

import flet as ft  # noqa: E402

from cs_music_player import ui as ui_mod  # noqa: E402
from cs_music_player.constants import (  # noqa: E402
    FONT_FAMILY,
    FONT_FAMILY_FILE,
    build_light_theme,
)
from cs_music_player.lyrics import LyricLine  # noqa: E402


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")
        fh.flush()


# ── 应用侧：记录歌词区实测高度 / 窗口行数 ── #

_orig_window_rows = ui_mod._lyric_window_rows


def _logged_window_rows(viewport_height: float, row_height: float) -> int:
    rows = _orig_window_rows(viewport_height, row_height)
    log(f"GEOM viewport_h={viewport_height} row_h={row_height} rows={rows}")
    return rows


ui_mod._lyric_window_rows = _logged_window_rows

LONG_LINE = "第10行-这是一条很长很长的歌词用来验证折行不会被裁切掉后半段内容"

LINES = [
    LyricLine(float(i), LONG_LINE if i == 9 else f"第{i + 1}行-测试歌词内容")
    for i in range(20)
]

# (阶段名, 窗口高度, 目标 active)
PLAN = [
    ("tall", 760, 9),
    ("tall", 760, 0),
    ("tall", 760, 19),
    ("short", 420, 9),
    ("short", 420, 0),
    ("short", 420, 19),
]


@ft.component
def Probe(page: ft.Page):
    active, set_active = ft.use_state(0)
    phase, set_phase = ft.use_state("tall")

    def run_plan() -> None:
        async def run() -> None:
            await asyncio.sleep(2.0)
            for step, (name, height, target) in enumerate(PLAN):
                if name != phase:
                    set_phase(name)
                    page.window.height = height
                    page.update()
                    await asyncio.sleep(1.6)
                set_active(target)
                log(f"STEP {step} phase={name} height={height} active={target}")
                await asyncio.sleep(2.6)
            log("DONE")

        page.run_task(run)

    ft.use_effect(run_plan, dependencies=[])

    return ft.Container(
        content=ui_mod.LyricsPanel(LINES, float(active) + 0.5, True, 0.0, 15.0),
        expand=True,
        bgcolor="#f0f0f0",
    )


def app_main(page: ft.Page) -> None:
    page.title = TITLE
    page.fonts = {FONT_FAMILY: FONT_FAMILY_FILE}
    page.theme = build_light_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#f0f0f0"
    page.padding = 0
    page.window.width = 760
    page.window.height = 760
    page.render(Probe, page)


# ── 驱动侧：窗口 / 截图 / 分析 ── #

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.GetWindowDC.restype = wt.HDC
user32.GetWindowDC.argtypes = [wt.HWND]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_uint]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


gdi32.GetDIBits.argtypes = [
    wt.HDC,
    wt.HBITMAP,
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.POINTER(BITMAPINFOHEADER),
    ctypes.c_uint,
]


def find_window(title: str, timeout: float = 40.0) -> int:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(0.4)
    return 0


def capture(hwnd: int):
    """PrintWindow 抓整窗 → (raw BGRA, w, h, 客户区偏移, 客户区尺寸)。"""
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    user32.PrintWindow(hwnd, memdc, 2)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)

    cli = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(cli))
    origin = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return (
        buf.raw,
        w,
        h,
        (origin.x - rect.left, origin.y - rect.top),
        (cli.right, cli.bottom),
    )


def bands_of(rows: list[int], gap: int = 4) -> list[tuple[int, int]]:
    """把连续（允许 gap 间断）的行号合并成带。"""
    out: list[tuple[int, int]] = []
    for y in rows:
        if out and y - out[-1][1] <= gap:
            out[-1] = (out[-1][0], y)
        else:
            out.append((y, y))
    return out


def analyze(raw: bytes, w: int, offset, client, tol_px: int) -> str:
    """找出文字带与蓝色（当前行）带，比较两者中心。"""
    off_x, off_y = offset
    cw, ch = client
    x0, x1 = off_x + 4, off_x + cw - 4
    y0, y1 = off_y, off_y + ch

    ink_rows: list[int] = []
    blue_rows: list[int] = []
    for y in range(y0, y1):
        base = y * w * 4
        ink = blue = 0
        for x in range(x0, x1, 2):
            o = base + x * 4
            b, g, r = raw[o], raw[o + 1], raw[o + 2]
            if b - r > 60 and b > 120:
                blue += 1
            if r < 205 and g < 205:
                ink += 1
        if ink > 3:
            ink_rows.append(y)
        if blue > 2:
            blue_rows.append(y)

    ink_bands = bands_of(ink_rows)
    blue_bands = bands_of(blue_rows)
    if not ink_bands or not blue_bands:
        return f"未找到文字带：ink={len(ink_rows)} blue={len(blue_rows)}"

    panel_center = (y0 + y1) / 2
    blue_top, blue_bottom = blue_bands[0]
    blue_center = (blue_top + blue_bottom) / 2
    delta = blue_center - panel_center

    blue_index = next(
        (i for i, (t, b) in enumerate(ink_bands) if t <= blue_center <= b),
        -1,
    )
    heights = [b - t + 1 for t, b in ink_bands]
    offsets = [round(((t + b) / 2 - panel_center) / 1.75, 1) for t, b in ink_bands]
    ok = abs(delta) <= tol_px
    return (
        f"{'OK ' if ok else 'FAIL'} 客户区=[{y0},{y1}] 中心={panel_center:.1f} "
        f"| 当前行 ink=[{blue_top},{blue_bottom}] 中心={blue_center:.1f} Δ={delta:+.1f}px "
        f"| 文字带 {len(ink_bands)} 个，当前行是第 {blue_index + 1} 个，带高={heights} "
        f"| 各行中心相对面板中心(逻辑px)={offsets}"
        f" (row_h≈57.5, 预期 Δ≈0，容差 ±{tol_px}px)"
    )


def write_png(path: str, raw: bytes, w: int, h: int, line_y: int) -> None:
    """BGRA → PNG，并在 line_y 画一条洋红线标出面板中线。"""
    import struct
    import zlib

    data = bytearray()
    for y in range(h):
        data.append(0)  # filter: none
        line = raw[y * w * 4 : (y + 1) * w * 4]
        for x in range(w):
            o = x * 4
            r, g, b = line[o + 2], line[o + 1], line[o]
            if abs(y - line_y) <= 1:
                r = g = 255
                b = 0
            data += bytes((r, g, b))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(data), 6))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(png)
    log(f"SHOT 已保存 {path}")


def drive() -> None:
    try:
        hwnd = find_window(TITLE)
        if not hwnd:
            log("ERROR 窗口未出现")
            os._exit(3)
        log(f"WINDOW hwnd={hwnd}")
        seen = -1
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            step_line = None
            try:
                with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        if line.startswith("STEP"):
                            step_line = line.strip()
                        elif line.startswith("DONE"):
                            step_line = "DONE"
            except OSError:
                pass
            if step_line == "DONE":
                log("DRIVER 计划执行完毕")
                break
            if step_line and step_line != seen:
                seen = step_line
                time.sleep(1.2)  # 等布局与动画稳定
                raw, w, h, offset, client = capture(hwnd)
                result = analyze(raw, w, offset, client, tol_px=4)
                log(f"CASES {seen} -> {result}")
                if seen.startswith("STEP 0 "):
                    center_y = offset[1] + int(client[1] / 2)
                    write_png(
                        os.path.join(PROBE_DIR, "proof_step0.png"),
                        raw,
                        w,
                        h,
                        center_y,
                    )
            time.sleep(0.2)

        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        os.system(f"taskkill /F /PID {pid.value} >nul 2>&1")
    except BaseException as exc:  # noqa: BLE001
        import traceback

        log(f"DRIVER ERROR {exc!r}\n{traceback.format_exc()}")
    finally:
        os._exit(0)


def main() -> None:
    if os.path.exists(LOG):
        os.remove(LOG)
    log(f"START {time.strftime('%H:%M:%S')}")
    threading.Thread(target=drive, daemon=True).start()
    threading.Timer(120.0, lambda: os._exit(3)).start()
    ft.run(app_main, assets_dir=os.path.join(PROJECT, "assets"))


if __name__ == "__main__":
    main()
