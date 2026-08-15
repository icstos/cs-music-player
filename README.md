# CS 音乐播放器

基于 [Flet](https://flet.dev/) 构建的本地音乐播放器，面向 Windows 桌面端，提供简洁、流畅的听歌体验。

## 功能特性

- **本地音乐播放** — 通过文件夹导入，支持 MP3、WAV、OGG、FLAC、M4A、AAC
- **播放控制** — 播放/暂停、上一曲/下一曲、进度拖拽、音量调节
- **播放模式** — 顺序播放、单曲循环、随机播放
- **歌词显示** — 自动匹配 `lyrics/` 子目录中的 `.lrc` / `.txt` 歌词，LRC 支持时间轴高亮；播放时自动从 [LRCLIB](https://lrclib.net) 后台下载缺失歌词到 `lyrics/` 子目录
- **专辑封面** — 从音频内嵌标签提取封面（基于 mutagen）
- **收藏与搜索** — 收藏曲目持久化保存，支持按歌名、歌手、文件夹名搜索，可筛选仅显示收藏
- **亮暗主题** — Material 3 界面，工具栏一键切换 **浅色 / 深色 / 跟随系统**（太阳 / 月亮 / 自动图标），选择持久化保存，重启后保留
- **最近文件夹历史** — 工具栏历史菜单记录最近打开的文件夹，悬停显示完整路径，支持一键**固定常用文件夹**置顶与**清空历史**，固定项独立持久化
- **曲目信息悬浮提示** — 鼠标悬停列表项显示专辑、文件大小、采样率、码率、声道、格式等元数据
- **列表信息增强** — 歌曲名称下方左侧显示歌手/艺术家，右侧显示时长
- **命令行启动路径** — 支持通过 exe / 命令行参数传入音乐文件，启动后直接定位播放该曲

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) ≥ 0.11（项目使用 uv 管理依赖与虚拟环境）
- Windows（主要开发与测试平台；其他平台未充分验证）

## 快速开始

### 1. 克隆并进入项目

```bash
git clone <repository-url>
cd cs-music-player
```

### 2. 同步依赖（自动创建虚拟环境）

```powershell
uv sync
```

首次运行会依据 `pyproject.toml` + `uv.lock` 创建 `.venv` 并安装全部依赖（含 dev 测试依赖）。

### 3. 启动应用

```powershell
uv run python main.py
```

直接传入音频文件或文件夹会自动定位播放该曲目：

```powershell
uv run python main.py "D:\音乐\晴天.mp3"
```

启动后点击右上角 **「导入音乐」** 按钮，选择包含音频文件的目录即可开始播放。

### 常用 uv 命令

| 命令 | 用途 |
|------|------|
| `uv sync` | 安装/同步 `uv.lock` 锁定的依赖 |
| `uv add <pkg>` | 添加运行时依赖并更新锁文件 |
| `uv add --group dev <pkg>` | 添加 dev 组依赖（如 `pytest`） |
| `uv run <cmd>` | 在项目虚拟环境中执行命令 |
| `uv lock` | 重新解析并生成 `uv.lock` |

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

## 自动下载歌词

播放缺少歌词的曲目时，应用会在后台从 [LRCLIB](https://lrclib.net) 查询并下载歌词，
保存到音乐文件夹的 `lyrics/` 子目录（文件名为 `曲名.lrc`，纯歌词则保存为 `.txt`）。
已存在本地歌词的曲目不会重复下载；下载请求已按 LRCLIB 规范设置 `User-Agent`、
串行节流并遵守 `Retry-After`，避免触发限流。

## 项目结构

```
cs-music-player/
├── main.py                  # 应用入口
├── pyproject.toml           # 项目配置、运行/dev 依赖声明
├── uv.lock                  # uv 锁定依赖版本（提交到版本库）
├── cs_music_player/
│   ├── app.py               # 顶层组件：状态管理、布局组装、事件桥接
│   ├── audio_player.py      # 播放器核心：曲目/元数据加载、播放控制
│   ├── ui.py                # UI 组件：播放列表、进度条、歌词面板、悬浮提示等
│   ├── lyrics.py            # 歌词扫描与 LRC 解析
│   ├── lrclib.py            # LRCLIB 歌词下载（后台查询与保存）
│   ├── store.py             # 收藏、最近文件夹、固定文件夹、主题持久化
│   ├── startup.py           # 命令行启动路径解析
│   ├── constants.py         # 格式、播放模式、亮/暗调色板、图标映射
│   └── __init__.py
├── tests/                   # pytest 单元测试
│   ├── test_lrclib.py
│   ├── test_player_modes.py
│   ├── test_player_state_sync.py
│   ├── test_progress_utils.py
│   └── test_recent_folders.py
└── scripts/
    └── smoke_test.py        # 封面提取与收藏逻辑的冒烟测试
```

## 技术栈

| 依赖 | 用途 |
|------|------|
| [flet](https://flet.dev/) ≥ 0.86 | 声明式 UI 框架（`@ft.component`、`use_state`、`use_effect`） |
| [flet-audio](https://pypi.org/project/flet-audio/) ≥ 0.86 | 音频播放 |
| [mutagen](https://pypi.org/project/mutagen/) ≥ 1.47 | 读取时长、标签（歌手/专辑）、采样率/码率、内嵌封面 |
| [pytest](https://docs.pytest.org/) ≥ 8.0 | 单元测试（dev 组） |

## 架构说明

应用采用 **声明式组件 + 单向数据流** 的组织方式：

- `PlayerApp`（`app.py`）集中持有 UI 状态，通过 `PlayerCallbacks` 接收播放器事件
- `Player`（`audio_player.py`）封装 `flet-audio`，在 Windows 上通过重建 `Audio` 控件（`autoplay=True`）规避 `audio.play()` 超时问题
- `ui.py` 中的子组件均为纯函数式 `@ft.component`，由 props 驱动重渲染，无需手动 `update()`
- **主题系统** — `constants.py` 定义亮/暗两套调色板，通过全局 `palette` 对象按需读取；切换模式时同步更新 `page.theme_mode` 与调色板，组件重渲染即应用新配色。主题模式、收藏、最近/固定文件夹均通过 Flet `SharedPreferences` 服务持久化（以曲目绝对路径为唯一标识）
- **选中与播放分离** — 单击列表项仅选中（不打断正在播放的歌曲），双击才真正切换播放

## 开发

### 运行测试

```powershell
uv run python -m pytest tests -q
```

测试覆盖：播放模式切换、进度条边界、最近文件夹/固定文件夹、主题持久化、LRCLIB 匹配与标签解析等。

### 冒烟测试

```powershell
uv run python scripts/smoke_test.py
```

测试封面提取（需项目根目录存在 `viper.mp3`）与收藏状态切换逻辑。

### 主要模块导出

```python
from cs_music_player import Player, Track, load_tracks_from_directory
from cs_music_player.constants import SUPPORTED_FORMATS, MODE_SEQUENCE, palette
```

## 许可证

暂未指定。使用前请根据仓库实际情况补充许可信息。