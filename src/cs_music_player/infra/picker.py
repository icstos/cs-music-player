"""系统目录选择框（Flet ``FilePicker``）。"""

from __future__ import annotations

import flet as ft

__all__ = ["FletDirectoryPicker", "install_directory_picker"]


def install_directory_picker(page: ft.Page) -> "FletDirectoryPicker":
    """创建并挂载 ``FilePicker`` 服务。"""
    picker = FletDirectoryPicker()
    page.services.append(picker.control)
    return picker


class FletDirectoryPicker:
    """``DirectoryPickerPort`` 的 Flet 实现。"""

    def __init__(self, inner: ft.FilePicker | None = None) -> None:
        self._inner = inner if inner is not None else ft.FilePicker()

    @property
    def control(self) -> ft.FilePicker:
        """底层 Flet 服务控件（需要挂到 ``page.services`` 上）。"""
        return self._inner

    async def pick_directory(self, title: str) -> str | None:
        """弹出目录选择框；用户取消时返回 ``None``。"""
        return await self._inner.get_directory_path(title)
