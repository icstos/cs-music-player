"""界面语义：本项目的每一处「该用哪个 M3 角色」都登记在这里。

为什么要多这一层：cs-ui 的颜色是 **46 个 Material 3 角色**（``PRIMARY`` /
``SURFACE_CONTAINER_LOW`` / ``ON_SURFACE_VARIANT`` …），直接写在组件里会立刻
出现两个问题 ——

1. **同一个位置被写成不同的档**：顶栏底色这处写 ``SURFACE``、那处写
   ``SURFACE_CONTAINER``，切到深色就露出一深一浅两条带；
2. **角色名当设计意图用**：读代码的人得先反推「这个 OUTLINE 是描边还是文字」。

于是这里把「界面上的语义」定成常量，组件只引用语义名：

======================  =====================================  ====================
语义                    角色                                   什么时候用
======================  =====================================  ====================
``CANVAS``               ``SURFACE``                            内容区（歌词、封面）底色
``PANEL``                ``SURFACE_CONTAINER_LOW``              顶栏 / 侧栏 / 播放栏
``PANEL_HIGH``           ``SURFACE_CONTAINER_HIGH``             面板上的次级块（搜索框、胶囊）
``LINE``                 ``OUTLINE_VARIANT``                    1px 分隔线、描边
``TEXT``                 ``ON_SURFACE``                         正文、标题
``TEXT_SOFT``            ``ON_SURFACE_VARIANT``                 次要信息（歌手、时长）
``ACCENT``               ``TERTIARY``                           点缀（睡眠、桌面歌词、收藏）
``SELECTED_BG``          ``PRIMARY_CONTAINER``                  选中行底色
``SELECTED_TEXT``        ``ON_PRIMARY_CONTAINER``               选中行文字
======================  =====================================  ====================

**全是角色名、不是色值**：Flutter 在绘制时解析，切主题 / 切明暗不需要 Python
重算任何东西，也不会出现「Python 换了色、已上屏的控件还是旧色」的半拍。
只在这三种情况下才用算出来的 hex（``ui.core.tokens`` 的 ``semantic_*``）：
状态色（成功 / 警告 / 危险）、需要透明叠加的底纹（``accent_soft``）、图表配色。
"""

from __future__ import annotations

from ui import Colors

__all__ = [
    "ACCENT",
    "CANVAS",
    "LINE",
    "PANEL",
    "PANEL_HIGH",
    "SELECTED_BG",
    "SELECTED_TEXT",
    "TEXT",
    "TEXT_SOFT",
    "TRACK",
    "TRACK_ACTIVE",
]

# ── 层次 ── #

#: 内容区底色（歌词、封面）。整个界面最「平」的一层。
CANVAS: str = Colors.SURFACE
#: 固定的功能面板：顶栏、侧栏、底部播放栏。
PANEL: str = Colors.SURFACE_CONTAINER_LOW
#: 面板上的次级块：搜索框、筛选胶囊、歌词工具条。
PANEL_HIGH: str = Colors.SURFACE_CONTAINER_HIGH

# ── 描边与文字 ── #

#: 1px 分隔线 / 描边。比 ``OUTLINE`` 淡一档，用来「分开」而不是「框住」。
LINE: str = Colors.OUTLINE_VARIANT
#: 正文与标题。
TEXT: str = Colors.ON_SURFACE
#: 次要信息：歌手、时长、计数、说明。
TEXT_SOFT: str = Colors.ON_SURFACE_VARIANT

# ── 强调与状态 ── #

#: 点缀色：与主色同族、退后一级，用在睡眠定时器、桌面歌词、收藏这些「次强调」。
ACCENT: str = Colors.TERTIARY
#: 选中行底色 / 文字。
SELECTED_BG: str = Colors.PRIMARY_CONTAINER
SELECTED_TEXT: str = Colors.ON_PRIMARY_CONTAINER

# ── 滑轨 ── #

#: 进度 / 音量滑轨：走过的一段是主色，没走过的是描边色。
TRACK_ACTIVE: str = Colors.PRIMARY
TRACK: str = Colors.OUTLINE_VARIANT
