"""共享常量：文件格式、播放模式、速度、歌词版式、桌面歌词尺寸。

配色也不在这里：每套配色只有一个「品牌色种子」，46 个界面角色由 cs-ui 的
色板引擎从种子解算（见 :data:`~cs_music_player.models.THEME_SEEDS`）。
字体也不在这里：正文字体族由 cs-ui 按运行平台选择（见 ``ui.core.fonts``）。
本模块不依赖任何第三方库。
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

#: 单行文本的自然高度比例：一个 size 号的文本行按 size × LYRIC_LINE_FACTOR
#: 计高。它是行距计算的布局约定（字族由 cs-ui 按平台选择，不绑定某一款字体）。
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
