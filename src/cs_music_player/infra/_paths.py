"""项目资源目录（assets）的唯一出口。

src 布局下包又深了一层，任何「向上数 N 层找 assets」的写法都会失效且**不报错**
（字体加载不出来、封面读不到，但程序照常启动）。统一从这里取：从当前文件向上
逐级查找真实存在的 ``assets`` 目录，命中即返回。

放在 infra 层是因为资源定位属于底层技术实现；所有需要 assets 的适配器都从此
模块取名，避免各自硬编码相对层数。
"""

from __future__ import annotations

from pathlib import Path

_ASSETS_NAME = "assets"


def assets_dir() -> Path:
    """返回项目资源目录；找不到时返回项目根下的预期位置，由调用方决定降级。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _ASSETS_NAME
        if candidate.is_dir():
            return candidate
    # src/<project>/infra/_paths.py 的上四级为项目根；正常情况下上面的循环已命中，
    # 这里只是给「assets 尚未生成」的极端情况一个稳定的预期位置。
    return here.parents[3] / _ASSETS_NAME
