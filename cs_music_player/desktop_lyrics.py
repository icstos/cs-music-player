"""桌面歌词窗：独立于主窗口的原生悬浮窗（Win32 分层窗口）。

**为什么不用 flet 再开一个窗口**：flet 1.0 的桌面端仍不支持从 Python 侧创建第二个
原生窗口（官方在等 flutter/flutter#142845），现成的多视图机制是给 Web 会话用的。
而桌面歌词要的「独立悬浮 + 置顶 + 鼠标穿透」恰好是 Win32 分层窗口的强项，于是这里
用 ctypes 直接建窗，用 Pillow 画帧（见 :mod:`cs_music_player.desktop_lyric_render`）。

关键取舍：

- **每像素 alpha 的 ``UpdateLayeredWindow``**，而不是 ``SetLayeredWindowAttributes``：
  前者能画出圆角、柔和投影和半透明工具条，也只有它能让「完全透明的像素不挡鼠标」
  （Windows 对分层窗口的命中测试按 alpha 做）。于是未锁定时，用户仍然能点到歌词
  周围的桌面；锁定时再加 ``WS_EX_TRANSPARENT``，整个窗一起穿透。
- **自带消息循环的独立线程**：窗口必须有自己的消息泵，而 flet 的 asyncio 循环在
  主线程上。跨线程只做「写状态 + ``PostMessage``」，帧的渲染全部发生在窗口线程，
  不需要任何锁保护 PIL。
- **``WS_EX_NOACTIVATE`` + ``WS_EX_TOOLWINDOW``**：点歌词不会抢走主窗口的键盘焦点，
  也不会在任务栏/Alt+Tab 里多出一个条目。
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field

from .desktop_lyric_render import (
    FONT_SIZE_DEFAULT,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    FONT_SIZE_STEP,
    Frame,
    render_frame,
    set_font_path,
    to_premultiplied_bgra,
)

IS_WINDOWS = sys.platform == "win32"

#: 锁定后给用户看的气泡时长（秒）。
HINT_SECONDS = 2.6
_LOCK_HINT = "歌词已锁定 · 在播放器主界面可解锁"

#: 默认停放位置：屏幕底部往上留出的比例。
DEFAULT_BOTTOM_MARGIN = 96

#: 悬浮窗宽度上限 = 所在显示器工作区宽度 × 该比例。
#: 桌面歌词是「一行一屏」的展示，超长行用省略号收尾，不允许撑破屏幕。
MAX_WIDTH_RATIO = 0.72


# ── 状态与对外配置 ── #


@dataclass
class DesktopLyricConfig:
    """桌面歌词的持久化配置。"""

    enabled: bool = False
    locked: bool = False
    font_size: float = FONT_SIZE_DEFAULT
    #: 窗口左上角（物理像素，屏幕坐标）；``None`` 表示用默认位置。
    x: float | None = None
    y: float | None = None

    def clamp_font(self) -> None:
        self.font_size = round(
            min(FONT_SIZE_MAX, max(FONT_SIZE_MIN, float(self.font_size))), 1
        )


@dataclass
class _ViewState:
    """窗口线程读取的视图状态（由外部线程写入）。"""

    lines: list[str] = field(default_factory=list)
    active: int = -1
    playing: bool = False
    font_size: float = FONT_SIZE_DEFAULT
    locked: bool = False
    visible: bool = False
    hint: str | None = None
    hint_deadline: float = 0.0


# ── Win32 绑定 ── #

if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    WS_POPUP = 0x80000000
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOPMOST = 0x00000008
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000

    GWL_EXSTYLE = -20
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010

    SW_HIDE = 0
    SW_SHOWNOACTIVATE = 4

    ULW_ALPHA = 0x00000002
    AC_SRC_OVER = 0x00
    AC_SRC_ALPHA = 0x01
    DIB_RGB_COLORS = 0

    WM_DESTROY = 0x0002
    WM_CLOSE = 0x0010
    WM_PAINT = 0x000F
    WM_ERASEBKGND = 0x0014
    WM_MOUSEMOVE = 0x0200
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONUP = 0x0205
    WM_MOUSELEAVE = 0x02A3
    WM_SETCURSOR = 0x0020
    WM_TIMER = 0x0113
    WM_NCLBUTTONDOWN = 0x00A1
    WM_EXITSIZEMOVE = 0x0232
    WM_DISPLAYCHANGE = 0x007E
    WM_DPICHANGED = 0x02E0
    WM_APP = 0x8000

    HTCAPTION = 2
    HTCLIENT = 1
    IDC_ARROW = 32512
    IDC_HAND = 32649
    IDC_SIZEALL = 32646
    TME_LEAVE = 0x00000002

    MF_STRING = 0x00000000
    MF_SEPARATOR = 0x00000800
    MF_CHECKED = 0x00000008
    TPM_RETURNCMD = 0x0100
    TPM_RIGHTBUTTON = 0x0002

    #: 自定义消息：重画一帧 / 应用一次配置。
    WM_LYRIC_RENDER = WM_APP + 1
    #: 提示气泡的定时器 id。
    TIMER_HINT = 1

    # 菜单命令 id
    CMD_LOCK = 1001
    CMD_FONT_INC = 1002
    CMD_FONT_DEC = 1003
    CMD_FONT_RESET = 1004
    CMD_CENTER = 1005
    CMD_CLOSE = 1006

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [
            ("BlendOp", ctypes.c_byte),
            ("BlendFlags", ctypes.c_byte),
            ("SourceConstantAlpha", ctypes.c_byte),
            ("AlphaFormat", ctypes.c_byte),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 3),
        ]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", ctypes.c_uint),
            ("lpfnWndProc", ctypes.c_void_p),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class TRACKMOUSEEVENT(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("hwndTrack", wintypes.HWND),
            ("dwHoverTime", wintypes.DWORD),
        ]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    _WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_longlong,
        wintypes.HWND,
        ctypes.c_uint,
        ctypes.c_ulonglong,
        ctypes.c_longlong,
    )

    _user32.DefWindowProcW.restype = ctypes.c_longlong
    _user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        ctypes.c_uint,
        ctypes.c_ulonglong,
        ctypes.c_longlong,
    ]
    _user32.CreateWindowExW.restype = wintypes.HWND
    _user32.LoadCursorW.restype = wintypes.HANDLE
    _user32.GetDC.restype = wintypes.HDC
    _user32.GetDC.argtypes = [wintypes.HWND]
    _user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _user32.UpdateLayeredWindow.restype = wintypes.BOOL
    _user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
        ctypes.POINTER(wintypes.POINT),
        ctypes.POINTER(wintypes.SIZE),
        wintypes.HDC,
        ctypes.POINTER(wintypes.POINT),
        wintypes.DWORD,
        ctypes.POINTER(BLENDFUNCTION),
        wintypes.DWORD,
    ]
    _user32.BeginPaint.restype = wintypes.HDC
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.PostMessageW.argtypes = [
        wintypes.HWND,
        ctypes.c_uint,
        ctypes.c_ulonglong,
        ctypes.c_longlong,
    ]
    _user32.SendMessageW.restype = ctypes.c_longlong
    _user32.CreatePopupMenu.restype = wintypes.HANDLE
    _user32.TrackPopupMenu.restype = wintypes.BOOL
    _user32.TrackPopupMenu.argtypes = [
        wintypes.HANDLE,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
    ]
    _user32.MonitorFromPoint.restype = wintypes.HANDLE
    _user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    # MonitorFromWindow 不声明 restype 会按 C int 返回，64 位下句柄被截断，
    # 随后 GetMonitorInfoW 直接失败。
    _user32.MonitorFromWindow.restype = wintypes.HANDLE
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]

    _gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    _gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(BITMAPINFO),
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    _gdi32.CreateCompatibleDC.restype = wintypes.HDC
    _gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    _gdi32.SelectObject.restype = wintypes.HANDLE

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _GetWindowLong = _user32.GetWindowLongPtrW
        _SetWindowLong = _user32.SetWindowLongPtrW
    else:  # pragma: no cover - 仅 32 位
        _GetWindowLong = _user32.GetWindowLongW
        _SetWindowLong = _user32.SetWindowLongW
    _GetWindowLong.restype = ctypes.c_longlong
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _SetWindowLong.restype = ctypes.c_longlong
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]

    # ctypes 在未声明 argtypes 时按 C int 传参，64 位下会把句柄/指针截断成
    # 32 位——表现是 CreateWindowExW 直接失败。凡是吃句柄、指针、LPCWSTR 的
    # 都要逐个声明，一个都不能省。
    _HWND_TOPMOST = ctypes.c_void_p(HWND_TOPMOST & 0xFFFFFFFFFFFFFFFF)
    _user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        ctypes.c_void_p,
    ]
    _user32.RegisterClassW.argtypes = [ctypes.c_void_p]
    _user32.DestroyWindow.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetTimer.restype = ctypes.c_void_p
    _user32.SetTimer.argtypes = [
        wintypes.HWND,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    _user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_void_p]
    _user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    _user32.SetCursor.restype = wintypes.HANDLE
    _user32.SetCursor.argtypes = [wintypes.HANDLE]
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    _user32.TrackMouseEvent.argtypes = [ctypes.POINTER(TRACKMOUSEEVENT)]
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.restype = ctypes.c_longlong
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.AppendMenuW.argtypes = [
        wintypes.HMENU,
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
    ]
    _user32.DestroyMenu.argtypes = [wintypes.HMENU]
    _user32.ReleaseCapture.argtypes = []
    _user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    _user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    _user32.GetDpiForWindow.restype = wintypes.UINT
    _user32.CreatePopupMenu.argtypes = []
    _gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    _gdi32.DeleteDC.argtypes = [wintypes.HDC]
    _gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    _gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]


def _enable_dpi_awareness() -> None:
    """把本进程设为 per-monitor-v2 DPI 感知。

    不设的话 Windows 会把窗口位图按 96 DPI 拉伸，在高分屏上整片发虚。flet 客户端
    是另一个进程，这里改的只是本进程（也就是这个悬浮窗）的坐标语义。
    """
    if not IS_WINDOWS:
        return
    for attempt in (
        lambda: _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)),
        lambda: _user32.SetProcessDPIAware(),
    ):
        try:
            if attempt():
                return
        except Exception:
            continue


class _Surface:
    """一块 32 位 top-down DIB + 其内存 DC，用于交给 ``UpdateLayeredWindow``。"""

    def __init__(self, screen_dc) -> None:
        self._screen_dc = screen_dc
        self.hdc = _gdi32.CreateCompatibleDC(screen_dc)
        self.hbitmap = None
        self.bits: ctypes.c_void_p | None = None
        self.width = 0
        self.height = 0
        self._old = None

    def ensure(self, width: int, height: int) -> None:
        if (width, height) == (self.width, self.height) and self.bits:
            return
        self.release_bitmap()
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        # 负高度 = top-down，行序与 Pillow 一致，省掉一次翻转。
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        bits = ctypes.c_void_p()
        self.hbitmap = _gdi32.CreateDIBSection(
            self._screen_dc, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        self.bits = bits
        self._old = _gdi32.SelectObject(self.hdc, self.hbitmap)
        self.width, self.height = width, height

    def write(self, data: bytes) -> None:
        ctypes.memmove(self.bits, data, len(data))

    def release_bitmap(self) -> None:
        if self.hbitmap:
            if self._old:
                _gdi32.SelectObject(self.hdc, self._old)
                self._old = None
            _gdi32.DeleteObject(self.hbitmap)
            self.hbitmap = None
            self.bits = None
        self.width = self.height = 0

    def release(self) -> None:
        self.release_bitmap()
        if self.hdc:
            _gdi32.DeleteDC(self.hdc)
            self.hdc = None


class DesktopLyrics:
    """桌面歌词悬浮窗。

    对外只有「设状态」和「设配置」两组方法，全部线程安全，可以从 flet 的回调里
    直接调用；窗口自身跑在一个独立线程上。

    事件通过两个回调回到调用方：

    - ``on_command(name)``：用户在悬浮窗上按了播放控制键（``prev`` / ``toggle`` /
      ``next``），需要宿主去驱动播放器。
    - ``on_config_change(config)``：锁定状态、字号或位置变了，宿主负责持久化。
    """

    CLASS_NAME = "CSMusicDesktopLyricWindow"
    WINDOW_TITLE = "CS 桌面歌词"

    def __init__(
        self,
        *,
        config: DesktopLyricConfig | None = None,
        on_command=None,
        on_config_change=None,
        font_path: str | None = None,
    ) -> None:
        if font_path:
            set_font_path(font_path)
        self._config = config or DesktopLyricConfig()
        self._config.clamp_font()
        self._on_command = on_command
        self._on_config_change = on_config_change

        self._lock = threading.Lock()
        self._view = _ViewState(
            font_size=self._config.font_size,
            locked=self._config.locked,
            visible=self._config.enabled,
        )
        self._hwnd = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._wndproc_ref = None
        self._surface: _Surface | None = None
        self._frame: Frame | None = None
        self._hovered = False
        self._hover_button: str | None = None
        self._pressed_button: str | None = None
        self._tracking_leave = False
        self._scale = 1.0
        self._dragging = False

    # —— 生命周期 —— #

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """建窗并起消息循环；重复调用无副作用。"""
        if not IS_WINDOWS:
            return False
        if self.running:
            return True
        _enable_dpi_awareness()
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._thread_main, name="desktop-lyrics", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5.0)
        return self._hwnd is not None

    def stop(self) -> None:
        hwnd = self._hwnd
        if hwnd and IS_WINDOWS:
            _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._hwnd = None

    # —— 视图状态（线程安全）—— #

    def set_lyrics(self, lines: list[str]) -> None:
        with self._lock:
            if lines == self._view.lines:
                return
            self._view.lines = list(lines)
        self._post_render()

    def set_active(self, index: int) -> None:
        with self._lock:
            if index == self._view.active:
                return
            self._view.active = index
        self._post_render()

    def set_playing(self, playing: bool) -> None:
        with self._lock:
            if playing == self._view.playing:
                return
            self._view.playing = playing
        self._post_render()

    def set_visible(self, visible: bool) -> None:
        self._config.enabled = bool(visible)
        with self._lock:
            self._view.visible = bool(visible)
        if visible:
            self.start()
        self._refresh_window()
        self._emit_config()

    @property
    def config(self) -> DesktopLyricConfig:
        return self._config

    def apply_config(self, config: DesktopLyricConfig) -> None:
        """应用持久化的配置（启动时调用一次）。

        这里必须把配置回传一次：宿主靠 ``on_config_change`` 把「桌面歌词是开着的」
        同步进它自己的界面状态，界面状态又决定要不要往悬浮窗推歌词。少了这一下，
        重启后悬浮窗会被建出来却永远停在「无歌词」的隐藏态。
        """
        self._config = config
        self._config.clamp_font()
        with self._lock:
            self._view.font_size = config.font_size
            self._view.locked = config.locked
            self._view.visible = config.enabled
        if config.enabled:
            self.start()
        else:
            self._refresh_window()
        self._emit_config()

    # —— 便捷操作 —— #

    def nudge_font(self, delta: float) -> None:
        self.set_font_size(self._config.font_size + delta)

    def set_font_size(self, size: float) -> None:
        config = self._config
        config.font_size = round(
            min(FONT_SIZE_MAX, max(FONT_SIZE_MIN, float(size))), 1
        )
        with self._lock:
            self._view.font_size = config.font_size
        self._refresh_window()
        self._emit_config()

    def set_locked(self, locked: bool, *, hint: bool = True) -> None:
        self._config.locked = bool(locked)
        with self._lock:
            self._view.locked = self._config.locked
            if locked and hint:
                self._view.hint = _LOCK_HINT
                self._view.hint_deadline = time.monotonic() + HINT_SECONDS
        self._refresh_window()
        self._emit_config()

    def center(self) -> None:
        """回到默认停放位置（屏幕底部居中）。"""
        if not IS_WINDOWS:
            return
        self._config.x = None
        self._config.y = None
        hwnd = self._hwnd
        if hwnd:
            left, top = self._default_origin(self._frame.width if self._frame else 400,
                                            self._frame.height if self._frame else 120)
            _user32.SetWindowPos(
                hwnd,
                _HWND_TOPMOST,
                left,
                top,
                0,
                0,
                SWP_NOSIZE | SWP_NOACTIVATE,
            )
            self._render()
        self._emit_config()

    # —— 内部：跨线程 —— #

    def _post_render(self) -> None:
        hwnd = self._hwnd
        if hwnd and IS_WINDOWS:
            _user32.PostMessageW(hwnd, WM_LYRIC_RENDER, 0, 0)

    def _refresh_window(self) -> None:
        """把锁定状态与显隐推给窗口（需要窗口线程去改扩展样式）。"""
        if not self.running:
            if self._config.enabled:
                self.start()
            return
        self._post_render()

    def _emit_config(self) -> None:
        if self._on_config_change is not None:
            try:
                self._on_config_change(self._config)
            except Exception:
                pass

    # —— 内部：窗口线程 —— #

    def _default_origin(self, width: int, height: int) -> tuple[int, int]:
        """默认停放位置：主屏工作区底部居中（避开任务栏）。"""
        monitor = _user32.MonitorFromPoint(wintypes.POINT(0, 0), 1)  # MONITOR_DEFAULTTOPRIMARY
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        _user32.GetMonitorInfoW(monitor, ctypes.byref(info))
        work = info.rcWork
        left = work.left + ((work.right - work.left) - width) // 2
        top = work.bottom - height - DEFAULT_BOTTOM_MARGIN
        return int(left), int(top)

    def _clamp_to_work_area(self, left: int, top: int, width: int, height: int):
        """把窗口位置夹回可见工作区，避免换分辨率后歌词跑到屏幕外。"""
        monitor = _user32.MonitorFromPoint(
            wintypes.POINT(int(left + width / 2), int(top + height / 2)), 2
        )  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        _user32.GetMonitorInfoW(monitor, ctypes.byref(info))
        work = info.rcWork
        left = max(work.left, min(int(left), work.right - 80))
        top = max(work.top, min(int(top), work.bottom - 40))
        return left, top

    def _thread_main(self) -> None:
        try:
            self._run_window()
        except Exception:
            import traceback

            traceback.print_exc()

    def _run_window(self) -> None:
        hinstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        self._wndproc_ref = _WNDPROC(self._on_message)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(self._wndproc_ref, ctypes.c_void_p)
        wc.hInstance = hinstance
        wc.hCursor = _user32.LoadCursorW(None, IDC_ARROW)
        wc.lpszClassName = self.CLASS_NAME
        _user32.RegisterClassW(ctypes.byref(wc))

        screen_dc = _user32.GetDC(None)
        self._surface = _Surface(screen_dc)

        ex_style = (
            WS_EX_LAYERED
            | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
            | (WS_EX_TRANSPARENT if self._config.locked else 0)
        )

        width = max(1, self._frame.width if self._frame else 400)
        height = max(1, self._frame.height if self._frame else 120)
        if self._config.x is None or self._config.y is None:
            left, top = self._default_origin(width, height)
        else:
            left, top = self._clamp_to_work_area(
                int(self._config.x), int(self._config.y), width, height
            )

        hwnd = _user32.CreateWindowExW(
            ex_style,
            self.CLASS_NAME,
            self.WINDOW_TITLE,
            WS_POPUP,
            left,
            top,
            width,
            height,
            None,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            _user32.ReleaseDC(None, screen_dc)
            self._ready.set()
            return
        self._hwnd = hwnd
        self._ready.set()

        if self._view.visible:
            _user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)

        self._render()
        self._message_loop()

        # —— 收尾 ——
        self._surface.release()
        self._surface = None
        _user32.ReleaseDC(None, screen_dc)
        self._hwnd = None

    def _message_loop(self) -> None:
        msg = wintypes.MSG()
        while True:
            result = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):
                return
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    # —— 内部：窗口消息 —— #

    def _on_message(self, hwnd, msg, wparam, lparam) -> int:
        try:
            if msg == WM_LYRIC_RENDER:
                self._render()
                return 0
            if msg == WM_MOUSEMOVE:
                self._on_mouse_move(hwnd, wparam, lparam)
                return 0
            if msg == WM_LBUTTONDOWN:
                self._on_lbutton_down(hwnd, lparam)
                return 0
            if msg == WM_LBUTTONUP:
                self._on_lbutton_up(hwnd, lparam)
                return 0
            if msg == WM_MOUSELEAVE:
                self._tracking_leave = False
                self._set_hover(False, None)
                return 0
            if msg == WM_SETCURSOR:
                return self._on_set_cursor(hwnd, lparam)
            if msg == WM_RBUTTONUP:
                self._popup_menu(hwnd)
                return 0
            if msg == WM_TIMER and wparam == TIMER_HINT:
                _user32.KillTimer(hwnd, TIMER_HINT)
                with self._lock:
                    self._view.hint = None
                self._render()
                return 0
            if msg == WM_EXITSIZEMOVE:
                self._dragging = False
                self._remember_position(hwnd)
                return 0
            if msg == WM_DPICHANGED or msg == WM_DISPLAYCHANGE:
                self._scale = self._dpi_scale(hwnd)
                self._render()
                return 0
            if msg == WM_ERASEBKGND:
                return 1
            if msg == WM_PAINT:
                # 分层窗口的内容由 UpdateLayeredWindow 直接给到合成器，
                # 这里只需把绘制区域标记为已处理，否则 WM_PAINT 会一直重发。
                return 0
            if msg == WM_CLOSE:
                _user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                _user32.PostQuitMessage(0)
                return 0
        except Exception:
            import traceback

            traceback.print_exc()
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _on_mouse_move(self, hwnd, wparam, lparam) -> None:
        # 拖动由系统接管（WM_NCLBUTTONDOWN/HTCAPTION），此间若鼠标已松开就该
        # 认为拖动结束——不能只依赖 WM_EXITSIZEMOVE，否则光标会一直停在拖动样式。
        if not wparam & 0x0001:
            self._dragging = False
        with self._lock:
            locked = self._view.locked
        if locked:
            return
        if not self._tracking_leave:
            track = TRACKMOUSEEVENT()
            track.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
            track.dwFlags = TME_LEAVE
            track.hwndTrack = hwnd
            _user32.TrackMouseEvent(ctypes.byref(track))
            self._tracking_leave = True

        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        self._set_hover(True, self._hit_test(x, y))

    def _on_lbutton_down(self, hwnd, lparam) -> None:
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        hit = self._hit_test(x, y)
        if hit is None:
            # 空白处按下 = 拖动窗口：交给系统做（比手动 SetWindowPos 跟手）。
            self._dragging = True
            point = wintypes.POINT()
            _user32.GetCursorPos(ctypes.byref(point))
            packed = ((point.y & 0xFFFF) << 16) | (point.x & 0xFFFF)
            _user32.ReleaseCapture()
            _user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, packed)
        else:
            self._pressed_button = hit

    def _on_lbutton_up(self, hwnd, lparam) -> None:
        pressed, self._pressed_button = self._pressed_button, None
        if not pressed:
            return
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        if self._hit_test(x, y) == pressed:
            self._invoke(pressed)

    def _on_set_cursor(self, hwnd, lparam) -> int:
        if lparam & 0xFFFF == HTCLIENT:
            point = wintypes.POINT()
            _user32.GetCursorPos(ctypes.byref(point))
            rect = RECT()
            _user32.GetWindowRect(hwnd, ctypes.byref(rect))
            hit = self._hit_test(point.x - rect.left, point.y - rect.top)
            if hit is not None:
                cursor = IDC_HAND
            elif self._dragging:
                cursor = IDC_SIZEALL
            else:
                cursor = IDC_SIZEALL
            _user32.SetCursor(_user32.LoadCursorW(None, cursor))
            return 1
        return _user32.DefWindowProcW(hwnd, WM_SETCURSOR, hwnd, lparam)

    def _set_hover(self, hovered: bool, button: str | None) -> None:
        if hovered == self._hovered and button == self._hover_button:
            return
        self._hovered = hovered
        self._hover_button = button
        self._render()

    def _hit_test(self, x: float, y: float) -> str | None:
        frame = self._frame
        if frame is None or not frame.buttons:
            return None
        for name, box in frame.buttons.items():
            if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                return name
        return None

    # —— 内部：菜单与命令 —— #

    def _popup_menu(self, hwnd) -> None:
        menu = _user32.CreatePopupMenu()
        flags_lock = MF_STRING | (MF_CHECKED if self._config.locked else 0)
        _user32.AppendMenuW(menu, flags_lock, CMD_LOCK, "锁定歌词（鼠标穿透）")
        _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        _user32.AppendMenuW(menu, MF_STRING, CMD_FONT_INC, "增大字体")
        _user32.AppendMenuW(menu, MF_STRING, CMD_FONT_DEC, "减小字体")
        _user32.AppendMenuW(menu, MF_STRING, CMD_FONT_RESET, "恢复默认字体")
        _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        _user32.AppendMenuW(menu, MF_STRING, CMD_CENTER, "回到默认位置")
        _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        _user32.AppendMenuW(menu, MF_STRING, CMD_CLOSE, "关闭桌面歌词")

        point = wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(point))
        # 菜单要在「点击外部即消失」需要本窗口是前台窗口；NOACTIVATE 的窗口
        # 不会被真正激活，因此这里只是满足 TrackPopupMenu 的前置条件。
        _user32.SetForegroundWindow(hwnd)
        command = _user32.TrackPopupMenu(
            menu,
            TPM_RETURNCMD | TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            hwnd,
            None,
        )
        _user32.PostMessageW(hwnd, 0, 0, 0)
        _user32.DestroyMenu(menu)
        if not command:
            return
        if command == CMD_LOCK:
            self.set_locked(not self._config.locked)
        elif command == CMD_FONT_INC:
            self.nudge_font(FONT_SIZE_STEP)
        elif command == CMD_FONT_DEC:
            self.nudge_font(-FONT_SIZE_STEP)
        elif command == CMD_FONT_RESET:
            self.set_font_size(FONT_SIZE_DEFAULT)
        elif command == CMD_CENTER:
            self.center()
        elif command == CMD_CLOSE:
            self._config.enabled = False
            with self._lock:
                self._view.visible = False
            self._refresh_window()
            self._emit_config()

    def _invoke(self, name: str) -> None:
        """工具条按钮 → 动作。"""
        if name == "lock":
            self.set_locked(True)
        elif name == "close":
            self._config.enabled = False
            with self._lock:
                self._view.visible = False
            self._refresh_window()
            self._emit_config()
        elif name == "font_inc":
            self.nudge_font(FONT_SIZE_STEP)
        elif name == "font_dec":
            self.nudge_font(-FONT_SIZE_STEP)
        elif name in ("prev", "toggle", "next") and self._on_command is not None:
            try:
                self._on_command(name)
            except Exception:
                pass

    def _remember_position(self, hwnd) -> None:
        rect = RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        self._config.x = float(rect.left)
        self._config.y = float(rect.top)
        self._emit_config()

    # —— 内部：绘制 —— #

    def _dpi_scale(self, hwnd) -> float:
        try:
            dpi = _user32.GetDpiForWindow(hwnd)
            if dpi:
                return max(0.5, dpi / 96.0)
        except Exception:
            pass
        dc = _user32.GetDC(None)
        try:
            return max(0.5, _gdi32.GetDeviceCaps(dc, 88) / 96.0)  # LOGPIXELSX
        finally:
            _user32.ReleaseDC(None, dc)

    def _current_frame(self) -> Frame:
        with self._lock:
            view = self._view
            lines = view.lines
            active = view.active
            playing = view.playing
            font_size = view.font_size
            hint = view.hint
            locked = view.locked
            if hint and time.monotonic() >= view.hint_deadline:
                view.hint = None
                hint = None

        if not lines:
            text, next_text, placeholder = "暂无歌词", None, True
        else:
            focus = active if active >= 0 else 0
            focus = min(focus, len(lines) - 1)
            text = lines[focus]
            next_text = lines[focus + 1] if focus + 1 < len(lines) else None
            placeholder = False

        return render_frame(
            text=text,
            next_text=next_text,
            font_size=font_size,
            scale=self._scale,
            hovered=self._hovered and not locked and hint is None,
            hover_button=self._hover_button,
            playing=playing,
            placeholder=placeholder,
            hint=hint,
            max_width=self._frame_width_limit(),
        )

    def _frame_width_limit(self) -> float | None:
        """画布宽度上限：所在显示器工作区宽度的 :data:`MAX_WIDTH_RATIO`。

        不设上限的话，一句超长歌词会把悬浮窗撑到屏幕外——既看不全，也无法拖回来。
        """
        try:
            hwnd = self._hwnd
            monitor = (
                _user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
                if hwnd
                else _user32.MonitorFromPoint(wintypes.POINT(0, 0), 1)
            )
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return None
            work = info.rcWork
            return max(120.0, (work.right - work.left) * MAX_WIDTH_RATIO)
        except Exception:
            return None

    def _render(self) -> None:
        hwnd = self._hwnd
        surface = self._surface
        if not hwnd or surface is None or not IS_WINDOWS:
            return

        self._scale = self._dpi_scale(hwnd)
        frame = self._current_frame()
        previous = self._frame
        self._frame = frame

        current = RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(current))
        current_w = current.right - current.left
        current_h = current.bottom - current.top
        left, top = current.left, current.top
        if previous is not None and previous.width != frame.width:
            # 宽度跟着歌词长短变，保持「中心不动」，视觉上文字不会左右跳。
            left = int(round(current.left + current_w / 2 - frame.width / 2))

        surface.ensure(frame.width, frame.height)
        surface.write(to_premultiplied_bgra(frame.image))

        if current_w != frame.width or current_h != frame.height:
            _user32.SetWindowPos(
                hwnd,
                _HWND_TOPMOST,
                left,
                top,
                frame.width,
                frame.height,
                SWP_NOACTIVATE,
            )

        screen_dc = _user32.GetDC(None)
        try:
            dst = wintypes.POINT(left, top)
            size = wintypes.SIZE(frame.width, frame.height)
            src = wintypes.POINT(0, 0)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            _user32.UpdateLayeredWindow(
                hwnd,
                screen_dc,
                ctypes.byref(dst),
                ctypes.byref(size),
                surface.hdc,
                ctypes.byref(src),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )
        finally:
            _user32.ReleaseDC(None, screen_dc)

        self._apply_lock(hwnd)
        self._apply_visibility(hwnd)
        self._sync_hint_timer(hwnd)

    def _apply_visibility(self, hwnd) -> None:
        """显示 / 隐藏悬浮窗。

        没有歌词时整窗隐藏——留一个孤零零的「暂无歌词」飘在桌面上是纯噪音，
        业界（网易云等）同样是「有词才出现」。主界面按钮的高亮状态负责说明
        「桌面歌词是开着的」。
        """
        with self._lock:
            should_show = self._view.visible and bool(self._view.lines)
        if should_show:
            _user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        else:
            _user32.ShowWindow(hwnd, SW_HIDE)

    def _sync_hint_timer(self, hwnd) -> None:
        with self._lock:
            hint = self._view.hint
            deadline = self._view.hint_deadline
        if not hint:
            return
        remaining = max(0.05, deadline - time.monotonic())
        _user32.SetTimer(hwnd, TIMER_HINT, int(remaining * 1000), None)

    # —— 内部：锁定 —— #

    def _apply_lock(self, hwnd) -> None:
        ex_style = _GetWindowLong(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        with self._lock:
            locked = self._view.locked
        if locked:
            ex_style |= WS_EX_TRANSPARENT
        else:
            ex_style &= ~WS_EX_TRANSPARENT
        _SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)
