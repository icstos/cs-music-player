"""启动参数解析：支持 exe / 命令行传入本地音乐文件路径。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_startup_path(argv: list[str] | None = None) -> Path | None:
    """解析首个可用的启动路径（文件或目录）。"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("paths", nargs="*")
    args, _ = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    for raw in args.paths:
        path = Path(raw).expanduser()
        if path.exists():
            return path.resolve()
    return None
