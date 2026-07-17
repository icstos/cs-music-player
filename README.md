# CS 音乐播放器

基于 [Flet](https://flet.dev/) 构建的本地音乐播放器，面向 Windows 桌面端，提供简洁、流畅的听歌体验。

## 功能特性

- **本地音乐播放** — 通过文件夹导入，支持 MP3、WAV、OGG、FLAC、M4A、AAC
- **播放控制** — 播放/暂停、上一曲/下一曲、进度拖拽、音量调节
- **播放模式** — 顺序播放、单曲循环、随机播放
- **歌词显示** — 自动匹配 `lyrics/` 子目录中的 `.lrc` / `.txt` 歌词，LRC 支持时间轴高亮
- **专辑封面** — 从音频内嵌标签提取封面（基于 mutagen）
- **收藏与搜索** — 收藏曲目持久化保存，支持按歌名/文件夹名搜索，可筛选仅显示收藏
- **主题适配** — Material 3 界面，跟随系统明暗模式自动切换

## 环境要求

- Python 3.12+
- Windows（主要开发与测试平台；其他平台未充分验证）

## 快速开始

### 1. 克隆并进入项目

```bash
git clone <repository-url>
cd cs-music-player
```

### 2. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 3. 启动应用

```powershell
python main.py
```

或使用 Flet CLI：

```powershell
flet run main.py
```

启动后点击右上角 **「打开文件夹」**，选择包含音频文件的目录即可开始播放。

## 音乐文件夹结构

播放器扫描所选目录**根层级**的音频文件（不递归子目录）。歌词放在同级 `lyrics/` 文件夹中，按文件名（不含扩展名）自动匹配：

```
my-music/
├── song1.mp3
├── song2.flac
└── lyrics/
    ├── song1.lrc      # 与 song1.mp3 匹配
    └── song2.txt      # 与 song2.flac 匹配
```

歌词文件支持 UTF-8 与 GBK 编码；`.lrc` 按时间轴解析，纯文本 `.txt` 则整段显示。

## 项目结构

```
cs-music-player/
├── main.py                  # 应用入口
├── pyproject.toml           # 项目配置与依赖
├── cs_music_player/
│   ├── app.py               # 顶层组件：状态管理、布局组装、事件桥接
│   ├── audio_player.py      # 播放器核心：曲目加载、播放控制
│   ├── ui.py                # UI 组件：播放列表、进度条、歌词面板等
│   ├── lyrics.py            # 歌词扫描与 LRC 解析
│   ├── store.py             # 收藏列表持久化
│   ├── constants.py         # 格式、播放模式、配色常量
│   └── __init__.py
└── scripts/
    └── smoke_test.py        # 封面提取与收藏逻辑的冒烟测试
```

## 技术栈

| 依赖 | 用途 |
|------|------|
| [flet](https://flet.dev/) ≥ 0.85.3 | 声明式 UI 框架（`@ft.component`、`use_state`、`use_effect`） |
| [flet-audio](https://pypi.org/project/flet-audio/) ≥ 0.85.3 | 音频播放 |
| [mutagen](https://pypi.org/project/mutagen/) ≥ 1.47 | 读取时长、内嵌封面 |

## 架构说明

应用采用 **声明式组件 + 单向数据流** 的组织方式：

- `PlayerApp`（`app.py`）集中持有 UI 状态，通过 `PlayerCallbacks` 接收播放器事件
- `Player`（`audio_player.py`）封装 `flet-audio`，在 Windows 上通过重建 `Audio` 控件（`autoplay=True`）规避 `audio.play()` 超时问题
- `ui.py` 中的子组件均为纯函数式 `@ft.component`，由 props 驱动重渲染，无需手动 `update()`
- 收藏数据通过 Flet `shared_preferences` 持久化，以曲目绝对路径为唯一标识

## 开发

### 冒烟测试

```powershell
python scripts/smoke_test.py
```

测试封面提取（需项目根目录存在 `viper.mp3`）与收藏状态切换逻辑。

### 主要模块导出

```python
from cs_music_player import Player, Track, load_tracks_from_directory
from cs_music_player.constants import SUPPORTED_FORMATS, MODE_SEQUENCE
```

## 许可证

暂未指定。使用前请根据仓库实际情况补充许可信息。
