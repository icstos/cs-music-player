"""探针：验证歌词区「歌词同步 / 字体大小」两个入口在真机上可用。

只渲染被测的那一小块（LyricSettingsEntry + LyricsPanel），用合成鼠标点击
两个入口并通过「应用侧状态日志 + 截图像素」双判据核对结果：

- 点「字体大小」入口 → 展开字号条 → 点 A+ / A- → 字号变化，且歌词行高真的跟着变；
- 点「歌词同步」入口 → 展开同步条 → 点「延后 1s」→ 当前高亮行真的移到上一行。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time

PROBE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = r"D:/Projects/cs-music-player"
LOG = os.path.join(PROBE_DIR, "lyric_settings_probe.log")
TITLE = "LYRIC_SETTINGS_PROBE"

sys.path.insert(0, PROJECT)

import flet as ft  # noqa: E402

from cs_music_player import ui as ui_mod  # noqa: E402
from cs_music_player.constants import (  # noqa: E402
    FONT_FAMILY,
    FONT_FAMILY_FILE,
    LYRIC_FONT_DEFAULT,
    LYRIC_FONT_MAX,
    LYRIC_FONT_MIN,
    build_light_theme,
)
from cs_music_player.lyrics import LyricLine  # noqa: E402


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")
        fh.flush()


# 行文本长度与行号成正比（第 N 行带 N 个 M）→ 墨迹量就是「哪一行」的指纹，
# 于是「歌词同步」是否真的把高亮行移了一行，可以用像素量证明。
LINES = [LyricLine(float(i), f"第{i + 1}行-" + "M" * (i + 1)) for i in range(20)]
POSITION = 9.5  # 基线：当前行 = 第 10 行（index 9）


# ── 应用侧 ── #


@ft.component
def Probe(page: ft.Page) -> ft.Control:
    offset, set_offset = ft.use_state(0.0)
    font, set_font = ft.use_state(LYRIC_FONT_DEFAULT)
    entry_h, set_entry_h = ft.use_state(0.0)

    def adjust_offset(delta: float) -> None:
        new = round(offset + delta, 3)
        log(f"APP offset {offset} -> {new}")
        set_offset(new)

    def adjust_font(delta: float) -> None:
        new = round(min(LYRIC_FONT_MAX, max(LYRIC_FONT_MIN, font + delta)), 1)
        log(f"APP font {font} -> {new}")
        set_font(new)

    def on_entry_size(e) -> None:
        if abs(e.height - entry_h) > 0.5:
            log(f"APP entry_box h={e.height} w={e.width}")
            set_entry_h(e.height)

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ui_mod.LyricSettingsEntry(
                        offset, font, "probe-track", adjust_offset, adjust_font
                    ),
                    on_size_change=on_entry_size,
                ),
                ft.Container(
                    content=ui_mod.LyricsPanel(
                        LINES, POSITION, True, offset=offset, font_size=font
                    ),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        ),
        expand=True,
        bgcolor="#ffffff",
    )


def app_main(page: ft.Page) -> None:
    page.title = TITLE
    page.fonts = {FONT_FAMILY: FONT_FAMILY_FILE}
    page.theme = build_light_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#ffffff"
    page.padding = 0
    page.window.width = 760
    page.window.height = 760
    page.render(Probe, page)


# ── Win32 ── #

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
user32.SetProcessDPIAware()
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.GetWindowDC.restype = wt.HDC
user32.GetWindowDC.argtypes = [wt.HWND]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_uint]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetWindowPos.argtypes = [
    wt.HWND,
    wt.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
]
user32.GetDpiForWindow.argtypes = [wt.HWND]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = ctypes.c_void_p(-1)


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


class Shot:
    """一次 PrintWindow 抓图 + 客户区几何。"""

    def __init__(self) -> None:
        pass

    def grab(self, hwnd: int) -> "Shot":
        rect = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        self.win = (rect.left, rect.top, rect.right, rect.bottom)
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
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hdc)

        cli = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(cli))
        origin = wt.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
        self.raw = buf.raw
        self.w, self.h = w, h
        self.ox, self.oy = origin.x - rect.left, origin.y - rect.top
        self.cw, self.ch = cli.right, cli.bottom
        self.dpr = user32.GetDpiForWindow(hwnd) / 96.0
        return self

    # —— 像素工具 —— #

    def _px(self, x: int, y: int) -> tuple[int, int, int]:
        o = (y * self.w + x) * 4
        return self.raw[o + 2], self.raw[o + 1], self.raw[o]  # r, g, b

    def ink_columns(self, y0: int, y1: int) -> list[int]:
        """「深色文字/图标」列：用于找顶部两个入口胶囊。"""
        cols = []
        for x in range(self.ox, self.ox + self.cw):
            hits = 0
            for y in range(y0, y1):
                r, g, b = self._px(x, y)
                if r < 200 and g < 200:
                    hits += 1
            if hits >= 2:
                cols.append(x)
        return cols

    def tint_columns(self, y0: int, y1: int) -> list[int]:
        """「浅蓝底色」列：pill_button / 胶囊高亮底色，用于找展开条上的按钮。"""
        cols = []
        for x in range(self.ox, self.ox + self.cw):
            hits = 0
            for y in range(y0, y1):
                r, g, b = self._px(x, y)
                if b - r > 18 and b > 228 and r > 170:
                    hits += 1
            if hits >= 3:
                cols.append(x)
        return cols

    def tint_rows(self, y0: int, y1: int) -> tuple[int, int] | None:
        """浅蓝底色的纵向范围——用来取按钮的垂直中点，而不是猜一个 y。"""
        rows = []
        for y in range(y0, min(y1, self.h)):
            hits = 0
            for x in range(self.ox, self.ox + self.cw, 2):
                r, g, b = self._px(x, y)
                if b - r > 18 and b > 228 and r > 170:
                    hits += 1
            if hits >= 4:
                rows.append(y)
        return (rows[0], rows[-1]) if rows else None

    def text_bands(self, y0: int, y1: int) -> list[tuple[int, int, bool, int]]:
        """墨迹行 → 文字带：返回 [(top, bottom, 是否蓝色当前行, 墨迹像素数)]。"""
        rows: list[tuple[int, bool, int]] = []
        for y in range(y0, min(y1, self.h)):
            ink = blue = 0
            for x in range(self.ox + 4, self.ox + self.cw - 4, 2):
                r, g, b = self._px(x, y)
                if r < 205 and g < 205:
                    ink += 1
                if b - r > 60 and b > 120:
                    blue += 1
            if ink > 3:
                rows.append((y, blue > 2, ink))
        bands: list[tuple[int, int, bool, int]] = []
        for y, is_blue, ink in rows:
            if bands and y - bands[-1][1] <= 4:
                top, _, prev_blue, prev_ink = bands[-1]
                bands[-1] = (top, y, prev_blue or is_blue, prev_ink + ink)
            else:
                bands.append((y, y, is_blue, ink))
        return bands


def clusters(cols: list[int], gap: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for x in cols:
        if out and x - out[-1][1] <= gap:
            out[-1] = (out[-1][0], x)
        else:
            out.append((x, x))
    return out


# ── 驱动侧 ── #


def find_window(title: str, timeout: float = 40.0) -> int:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(0.4)
    return 0


def attach_foreground(hwnd: int) -> bool:
    """挂接前台线程后再抢前台——单独 SetForegroundWindow 常被系统拒绝。"""
    fg = user32.GetForegroundWindow()
    tgt = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    cur = kernel32.GetCurrentThreadId()
    attached = bool(user32.AttachThreadInput(cur, tgt, True)) if tgt else False
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetActiveWindow(hwnd)
    return attached


def detach_foreground(attached: bool) -> None:
    if not attached:
        return
    fg = user32.GetForegroundWindow()
    tgt = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    if tgt:
        user32.AttachThreadInput(kernel32.GetCurrentThreadId(), tgt, False)


def click_once(sx: int, sy: int) -> None:
    user32.SetCursorPos(sx - 1, sy)
    time.sleep(0.15)
    user32.SetCursorPos(sx, sy)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
    time.sleep(0.45)


def last_entry_h() -> float:
    """从应用日志里取最近一次上报的入口区高度（逻辑 px）。"""
    value = 32.0
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("APP entry_box"):
                    value = float(line.split("h=")[1].split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return value


def report(shot: Shot, label: str, extra: str = "") -> None:
    dpr = shot.dpr
    entry_h = last_entry_h()

    chip_cols = shot.ink_columns(shot.oy + int(2 * dpr), shot.oy + int(24 * dpr))
    chips = clusters(chip_cols, int(8 * dpr))
    pill_cols = shot.tint_columns(shot.oy + int(30 * dpr), shot.oy + int(100 * dpr))
    pills = clusters(pill_cols, int(6 * dpr))

    bands = shot.text_bands(shot.oy + int((entry_h + 4) * dpr), shot.oy + shot.ch)
    centers = [round((t + b) / 2 / dpr, 1) for t, b, _, _ in bands]
    heights = [round((b - t + 1) / dpr, 1) for t, b, _, _ in bands]
    pitches = [
        round((centers[i + 1] - centers[i]), 1) for i in range(len(centers) - 1)
    ]
    blue = next((i for i, band in enumerate(bands) if band[2]), -1)
    blue_ink = bands[blue][3] if blue >= 0 else -1
    log(
        f"SHOT {label} entry_h={entry_h:.1f} chips={[(round(a / dpr), round(b / dpr)) for a, b in chips]} "
        f"pills={[(round(a / dpr), round(b / dpr)) for a, b in pills]} "
        f"bands={len(bands)} band_h={heights} pitch={pitches} blue_band={blue + 1}/{len(bands)} "
        f"blue_ink={blue_ink} ink_per_band={[band[3] for band in bands]} {extra}"
    )


# (标签, 动作)
PLAN = [
    ("baseline", "shot"),
    ("open_font", "click_font_toggle"),
    ("font_plus_1", "click_last_pill"),
    ("font_plus_2", "click_last_pill"),
    ("font_minus", "click_first_pill"),
    ("close_font", "click_font_toggle"),
    ("open_sync", "click_sync_toggle"),
    ("sync_delay_1s", "click_last_pill"),
]


def find_target(shot: Shot, kind: str) -> tuple[int, int] | None:
    """在截图上定位点击目标：返回窗口位图坐标系里的 (x, y)。"""
    dpr = shot.dpr
    if kind in ("click_font_toggle", "click_sync_toggle"):
        chips = clusters(
            shot.ink_columns(shot.oy + int(2 * dpr), shot.oy + int(24 * dpr)),
            int(8 * dpr),
        )
        log(f"LOOK {kind} chips={[(a, b) for a, b in chips]}")
        if len(chips) < 2:
            return None
        edge = chips[-1] if kind == "click_font_toggle" else chips[-2]
        return (edge[0] + edge[1]) // 2, shot.oy + int(13 * dpr)

    y0, y1 = shot.oy + int(28 * dpr), shot.oy + int(70 * dpr)
    pills = clusters(shot.tint_columns(y0, y1), int(6 * dpr))
    log(
        f"LOOK {kind} pills={[(a, b) for a, b in pills]} "
        f"tint_rows={shot.tint_rows(y0, y1)}"
    )
    if not pills:
        return None
    edge = pills[-1] if kind == "click_last_pill" else pills[0]
    rows = shot.tint_rows(y0, y1)
    y = (rows[0] + rows[1]) // 2 if rows else shot.oy + int(46 * dpr)
    return (edge[0] + edge[1]) // 2, y


def state_counts() -> tuple[int, int, int]:
    """应用日志里的变更条数（字号 / 偏移 / 入口区高度）。

    入口区高度算进去，是为了让「点开/收起」这类不改变字号状态的点击也能被判定成功——
    否则重试机制会把胶囊反复翻转（开关是两次点击一循环）。
    """
    font = offset = layout = 0
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("APP font"):
                    font += 1
                elif line.startswith("APP offset"):
                    offset += 1
                elif line.startswith("APP entry_box"):
                    layout += 1
    except OSError:
        pass
    return font, offset, layout


def drive() -> None:
    try:
        hwnd = find_window(TITLE)
        if not hwnd:
            log("ERROR 窗口未出现")
            os._exit(3)
        log(f"WINDOW hwnd={hwnd}")
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 40, 40, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
        )
        time.sleep(1.0)

        for label, action in PLAN:
            if action != "shot":
                shots: list[str] = []
                for attempt in range(1, 4):
                    shot = Shot().grab(hwnd)
                    before = state_counts()
                    target = find_target(shot, action)
                    if target is None:
                        log(f"SKIP {label}: 找不到点击目标")
                        break
                    rect = shot.win
                    # 第一次点击落在歌词区空白处：只用于激活窗口（否则首次点击会被系统吃掉）
                    attach_foreground(hwnd)
                    click_once(rect[0] + shot.ox + shot.cw // 2, rect[1] + shot.oy + shot.ch // 2)
                    click_once(rect[0] + target[0], rect[1] + target[1])
                    detach_foreground(True)
                    time.sleep(1.2)
                    after = state_counts()
                    shots.append(
                        f"try{attempt} at={target} screen=({rect[0] + target[0]},{rect[1] + target[1]}) "
                        f"state {'CHANGED' if after != before else 'unchanged'}"
                    )
                    if after != before:
                        break
                log(f"CLICK {label} {action} | " + " | ".join(shots))
            shot = Shot().grab(hwnd)
            report(shot, label)
            if label == "baseline":
                save_png(os.path.join(PROBE_DIR, "settings_probe_baseline.png"), shot)
            if label == "open_font":
                save_png(os.path.join(PROBE_DIR, "settings_probe_font_open.png"), shot)
            if label == "font_plus_2":
                save_png(os.path.join(PROBE_DIR, "settings_probe_font_18.png"), shot)
            if label == "open_sync":
                save_png(os.path.join(PROBE_DIR, "settings_probe_sync_open.png"), shot)

        log("DONE")
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        os.system(f"taskkill /F /PID {pid.value} >nul 2>&1")
    except BaseException as exc:  # noqa: BLE001
        import traceback

        log(f"DRIVER ERROR {exc!r}\n{traceback.format_exc()}")
    finally:
        os._exit(0)


def save_png(path: str, shot: Shot) -> None:
    import struct
    import zlib

    data = bytearray()
    for y in range(shot.h):
        data.append(0)
        row = shot.raw[y * shot.w * 4 : (y + 1) * shot.w * 4]
        for x in range(shot.w):
            o = x * 4
            data += bytes((row[o + 2], row[o + 1], row[o]))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", shot.w, shot.h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(data), 6))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as fh:
        fh.write(png)
    log(f"PNG 已保存 {path}")


def main() -> None:
    if os.path.exists(LOG):
        os.remove(LOG)
    log(f"START {time.strftime('%H:%M:%S')}")
    threading.Thread(target=drive, daemon=True).start()
    threading.Timer(180.0, lambda: os._exit(3)).start()
    ft.run(app_main, assets_dir=os.path.join(PROJECT, "assets"))


if __name__ == "__main__":
    main()
