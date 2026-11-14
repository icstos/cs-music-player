"""cs-ui 未覆盖的原生控件出口（视图层**唯一**允许出现 flet 的文件）。

为什么需要这一层：``ui.Slider`` / ``ui.Chip`` 是「带标签的表单控件」（observable
dataclass + ``.ui()``），不是控件本身。直接 ``from ui import Slider`` 拿到的是表单
组件——它自带标签排版、值吸附与 ``.ui()`` 构建，跟这里要的「裸滑轨 / 单个胶囊」
同名不同物，套上去会把播放条改造成一张表单。

所以这里显式指名 flet 的实现，并把它收成**一扇门**：

- 视图其余部分只认 ``ui`` 顶层导出的名字（不带框架前缀）；
- ``tests/test_architecture.py`` 卡住这条线——视图里新冒出一个原生控件名会立刻
  失败，必须回到这里显式登记并写明理由。
"""

from __future__ import annotations

from ui import ft

__all__ = ["PresetChip", "TrackSlider"]

#: 裸滑轨：进度与音量用。表单版没有 ``on_change_end``，进度条必须靠它在松手时 seek。
TrackSlider = ft.Slider

#: 单个可选胶囊：睡眠定时器的分钟预设。表单版 ``ui.Chip`` 是「一组选项 + 选中状态」，
#: 而这里每个胶囊点一下就立即生效，不需要维持选中态。
PresetChip = ft.Chip
