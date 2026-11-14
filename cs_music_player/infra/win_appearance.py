"""原生窗口外观：让 Windows 标题栏跟随应用的明暗主题。

Flet 只管 Flutter 画布，标题栏那一圈是系统画的。深色界面配白标题栏会像
「两个程序拼在一起」，所以这里用 DWM 的 ``DWMWA_USE_IMMERSIVE_DARK_MODE``
把标题栏也切过去。

**这一层只管「怎么切」，不决定「什么时候切」**：视图在主题变化时调用它，
组装根负责把标题传进去。任何一步失败都吞掉——为了标题栏颜色让程序起不来
不划算。
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

__all__ = ["set_dark_title_bar"]

#: Win10 20H1+ / Win11 用的属性号；更早的 1809~1909 是 19。
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY = 19

#: 只让窗口重画边框：不改位置、尺寸、层级，也不激活窗口。
_SWP_FRAMECHANGED = 0x0020
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010


def _user32() -> Any:
    if sys.platform != "win32":
        raise OSError("仅 Windows 支持")
    return ctypes.WinDLL("user32", use_last_error=True)


def _dwmapi() -> Any:
    if sys.platform != "win32":
        raise OSError("仅 Windows 支持")
    return ctypes.WinDLL("dwmapi", use_last_error=True)


def _find_window(title: str) -> int:
    """按标题找可见的顶层窗口，找不到返回 0。

    Flet 的窗口由客户端进程创建，拿不到句柄对象，只能按标题枚举。同名窗口
    取最后出现的那个（新窗口在枚举顺序里靠后）。
    """
    user32 = _user32()
    found: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    def visit(hwnd: Any, _param: Any) -> bool:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if buffer.value == title and user32.IsWindowVisible(hwnd):
            found.append(int(hwnd))
        return True

    user32.EnumWindows(callback_type(visit), 0)
    return found[-1] if found else 0


def set_dark_title_bar(title: str, dark: bool) -> bool:
    """把标题为 ``title`` 的窗口切成深 / 浅色标题栏。

    Returns:
        是否真的改成功（非 Windows、找不到窗口、DWM 不支持都返回 ``False``）。
    """
    try:
        hwnd = _find_window(title)
        if not hwnd:
            return False
        value = ctypes.c_int(1 if dark else 0)
        dwmapi = _dwmapi()
        applied = False
        for attribute in (
            _DWMWA_USE_IMMERSIVE_DARK_MODE,
            _DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY,
        ):
            if dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            ) == 0:
                applied = True
                break
        if not applied:
            return False
        # 标题栏由 DWM 绘制，属性改完要让它重画一次边框才生效
        _user32().SetWindowPos(
            ctypes.c_void_p(hwnd),
            None,
            0,
            0,
            0,
            0,
            _SWP_FRAMECHANGED
            | _SWP_NOMOVE
            | _SWP_NOSIZE
            | _SWP_NOZORDER
            | _SWP_NOACTIVATE,
        )
        return True
    except Exception:
        return False
