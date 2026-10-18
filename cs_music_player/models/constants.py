"""共享常量：文件格式、播放模式、速度、歌词版式、桌面歌词尺寸、本地字体。

配色不在这里：调色板由「配色主题 + 明暗」在视图层推导
（见 :mod:`cs_music_player.view.colors`），本模块不依赖任何第三方库。
"""

from __future__ import annotations

# ── 文件格式 ── #
AUDIO_EXTENSIONS: tuple[str, ...] = (
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".m4a",
    ".aac",
)
LYRIC_EXTENSIONS: tuple[str, ...] = (".lrc", ".txt")

#: 历史名字，语义等同于 :data:`AUDIO_EXTENSIONS`。
SUPPORTED_FORMATS: tuple[str, ...] = AUDIO_EXTENSIONS
#: 历史名字，语义等同于 :data:`LYRIC_EXTENSIONS`。
SUPPORTED_LYRICS_FORMATS: tuple[str, ...] = LYRIC_EXTENSIONS

# ── 播放速度 ── #
SPEED_PRESETS: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 4.0, 8.0)
SPEED_MIN: float = 0.25
SPEED_MAX: float = 8.0

# ── 歌词字体 ── #
LYRIC_FONT_DEFAULT: float = 15.0
LYRIC_FONT_MIN: float = 11.0
LYRIC_FONT_MAX: float = 24.0

#: 字体自带的单行高度比例：一个 size 号的文本行占 size × LYRIC_LINE_FACTOR 高。
#: 实测 AlibabaPuHuiTi（多行文本相邻行中心距 ÷ 字号 ≈ 1.40），与字体
#: hhea 的 asc 1060 + desc 340 / upem 1000 = 1.4 一致。
LYRIC_LINE_FACTOR: float = 1.4

#: 相邻两行歌词之间额外的呼吸空间，按字号比例给出。
#: 于是普通行高 = 字号 × (1.4 + 0.6) = 字号 × 2 —— 比「每行都预留折行后的两行高度」
#: 紧凑得多，同时仍留出 ≈0.6 字号的空白。所有普通行等高，是「当前行落在歌词区
#: 中线」的前提（行高不齐就得逐行量像素）。
LYRIC_ROW_GAP_RATIO: float = 0.6

#: 正在播放的行相对基准字号的放大增量（比普通行大一号以示强调）。
LYRIC_ACTIVE_DELTA: float = 3.0

#: 歌词同步微调的两个步长（秒）。界面上的「提前 / 延后 0.1s、1s」就是它们。
LYRIC_OFFSET_STEP_FINE: float = 0.1
LYRIC_OFFSET_STEP_COARSE: float = 1.0

# ── 睡眠定时器 ── #
#: 弹窗里的快捷预设（分钟）。
SLEEP_PRESET_MINUTES: tuple[int, ...] = (10, 15, 30, 45, 60)

# ── 桌面歌词（悬浮窗）── #
#: 桌面歌词的字号范围比主界面歌词面板宽得多：它是「隔着桌面看」的，默认就要大
#: 一号，且允许放得更大。
DESKTOP_LYRIC_FONT_DEFAULT: float = 26.0
DESKTOP_LYRIC_FONT_MIN: float = 16.0
DESKTOP_LYRIC_FONT_MAX: float = 56.0
DESKTOP_LYRIC_FONT_STEP: float = 2.0

# ── 用户数据 ── #
#: 最近打开文件夹最多保留几条。
MAX_RECENT_FOLDERS: int = 8

# ── 本地字体 ── #
FONT_FAMILY: str = "Alibaba PuHuiTi"
FONT_FAMILY_FILE: str = "/fonts/AlibabaPuHuiTi-3-55-Regular.otf"
