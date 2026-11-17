"""视图层格式化助手：时间、文件大小、采样率、码率、对齐文本与倍速。"""

from __future__ import annotations

__all__ = [
    "_fmt",
    "fmt_duration",
    "_fmt_size",
    "_fmt_frequency",
    "_fmt_bitrate",
    "_kv",
    "_fmt_speed",
]


def _fmt(seconds: float) -> str:
    """秒数 → ``m:ss`` 格式。"""
    if seconds <= 0 or seconds != seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def fmt_duration(seconds: float) -> str:
    """秒数 → 倒计时可读格式（``mm:ss`` / ``h:mm:ss``）。"""
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _fmt_size(size: int) -> str:
    """字节数 → 可读文件大小。"""
    if size <= 0:
        return ""
    if size >= 1 << 30:
        return f"{size / (1 << 30):.2f} GB"
    if size >= 1 << 20:
        return f"{size / (1 << 20):.1f} MB"
    return f"{size / (1 << 10):.0f} KB"


def _fmt_frequency(hz: int) -> str:
    """采样率 Hz → ``44.1 kHz``。"""
    if hz <= 0:
        return ""
    return f"{hz / 1000:g} kHz"


def _fmt_bitrate(bps: int) -> str:
    """码率 bps → ``320 kbps``。"""
    if bps <= 0:
        return ""
    return f"{bps / 1000:g} kbps"


def _kv(label: str, value: str) -> str:
    """生成两列对齐的键值行：标签宽度不足 4 个全角字符时补全角空格。"""
    return f"{label}{'　' * (4 - len(label))}{value}"


def _fmt_speed(rate: float) -> str:
    """倍速 → 可读标签，如 ``1.0x``、``1.25x``。"""
    return f"{rate:g}x"
