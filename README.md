# CS 音乐播放器

基于 [Flet](https://flet.dev/) 构建的本地音乐播放器，面向 Windows 桌面端，提供简洁、流畅的听歌体验。

## 功能特性

- **本地音乐播放** — 通过文件夹导入，支持 MP3、WAV、OGG、FLAC、M4A、AAC
- **播放控制** — 播放/暂停、上一曲/下一曲、进度拖拽、音量调节
- **播放模式** — 顺序播放、单曲循环、随机播放
- **歌词显示** — 自动匹配 `lyrics/` 子目录中的 `.lrc` / `.txt` 歌词，LRC 支持时间轴高亮，歌词按紧凑行距（字号 × 2）整屏铺开，当前播放行始终停在歌词区垂直中线上
 （可见行数随歌词区尺寸与字号自适应）；歌词区右上角提供 **歌词同步** 与 **字体大小** 两个入口；播放时自动从 [LRCLIB](https://lrclib.net) 后台下载缺失歌词到 `lyrics/` 子目录
- **专辑封面** — 从音频内嵌标签提取封面（基于 mutagen）
- **收藏与搜索** — 收藏曲目持久化保存，支持按歌名、歌手、文件夹名搜索，可筛选仅显示收藏
- **亮暗主题** — Material 3 界面，工具栏一键切换 **浅色 / 深色 / 跟随系统**（太阳 / 月亮 / 自动图标），选择持久化保存，重启后保留
- **最近文件夹历史** — 工具栏历史菜单记录最近打开的文件夹，悬停显示完整路径，支持一键**固定常用文件夹**置顶与**清空历史**，固定项独立持久化
- **桌面歌词悬浮窗** — 独立于主窗口的原生悬浮窗，逐像素透明、可鼠标穿透锁定、可拖动、右键菜单、悬停工具条（详见下文）
- **曲目信息悬浮提示** — 鼠标悬停列表项显示专辑、文件大小、采样率、码率、声道、格式等元数据
- **列表信息增强** — 歌曲名称下方左侧显示歌手/艺术家，右侧显示时长
- **命令行启动路径** — 支持通过 exe / 命令行参数传入音乐文件，启动后直接定位播放该曲
- **睡眠定时器** — 倒计时结束后自动关闭软件

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) ≥ 0.11（项目使用 uv 管理依赖与虚拟环境）
- Windows（主要开发与测试平台；桌面歌词悬浮窗依赖 Win32 分层窗口）

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

## 歌词同步与字号

歌词区右上角有两个独立入口（仅在当前曲目有歌词时出现）：点开各自展开一条工具条，
两者互斥展开，切换曲目时自动收起。

| 入口 | 作用 | 取值 | 生效范围 |
| --- | --- | --- | --- |
| 歌词同步 | 修正歌词与音频的时间差 | 提前 / 延后 `0.1s`、`1s` | **按曲目记忆**，改动后可一键恢复同步 |
| 字体大小 | 调整歌词字号 | `11`–`24` px，`A-` / `A+` 各一档 1px | **全局生效**，改动后可一键恢复默认 `15px` |

两个入口的图标/文字在「已展开」或「与默认值不同」时高亮，一眼能看出当前是否被调整过。
字号变化时歌词区按新的行高重算可见行数（正在播放的行仍停在垂直中线上）。

### 行距与版式

行距全部由字号推导（`cs_music_player/models/constants.py` 顶部三个常量），不写死像素：

| 量 | 取值 | 说明 |
| --- | --- | --- |
| 普通行高 | 字号 × `2.0` | `1.4` 是字体自带的单行高度（实测：多行文本相邻行中心距 ÷ 字号 ≈ 1.40，与字体 hhea 的 `asc 1060 + desc 340 / upem 1000` 一致），另 `0.6` 是行间留白 |
| 当前行字号 | 字号 + `3` | 放大一号以示强调 |
| 当前行高度 | 按内容自适应，最多两行 | 折行不会被裁；没折行时靠上下留白恰好与普通行等高 |

普通行固定为**一行**高，超长时以 `…` 收尾——等高是「当前行落在中线」的前提（行高不齐就得逐行量像素），
也让歌词区能显示更多行；正在播放的那一行则允许折两行并完整显示，高度由内容决定，
中心仍精确落在歌词区中线上（窗口上下两半的行数相等）。

## 桌面歌词悬浮窗

主界面工具栏的「桌面歌词」菜单可以开关、锁定、调字号、复位位置。
悬浮窗是 Win32 分层窗口（`WS_EX_LAYERED` + `UpdateLayeredWindow`），
每帧由 Pillow 渲染成预乘 BGRA 位图，因此支持圆角、柔和投影与半透明工具条；
未锁定时透明像素不参与命中测试，锁定时整窗鼠标穿透。配置（开关/锁定/字号/位置）
持久化保存，无歌词时整窗隐藏。

---

## 架构说明

程序采用 **MVVM + 分层依赖倒置**，五个层级严格单向依赖：

```
                    ┌────────────────────────────┐
                    │  view     （声明式 Flet UI）│
                    └──────────────┬─────────────┘
                                   │ 只读状态 / 只调方法
                    ┌──────────────▼─────────────┐
                    │  viewmodel（UI 状态 + 动作）│  纯 Python，零 Flet 依赖
                    └──────────────┬─────────────┘
                                   │
                    ┌──────────────▼─────────────┐
                    │  service  （业务流程编排）  │  只依赖 infra.ports
                    └──────────────┬─────────────┘
                                   │
                    ┌──────────────▼─────────────┐
                    │  infra    （技术实现 + 契约）│
                    └──────────────┬─────────────┘
                                   │
        models（数据结构 / 枚举 / 常量）— 所有层都可以依赖
```

| 层 | 目录 | 职责 | 允许依赖 |
| --- | --- | --- | --- |
| models | `cs_music_player/models/` | 数据结构、状态枚举、常量。**无任何业务逻辑** | 仅标准库 |
| infra | `cs_music_player/infra/` | 封装底层技术，对外只暴露 `infra/ports.py` 里的 `Protocol` | 标准库、flet / mutagen / Pillow、models |
| service | `cs_music_player/service/` | 编排核心业务流程 | models、**仅** `infra.ports` |
| viewmodel | `cs_music_player/viewmodel/` | 持有 UI 状态、暴露动作、连接 View 与 Service | models、service |
| view | `cs_music_player/view/` | 纯 Flet 声明式渲染与事件分发，无业务逻辑 | models、viewmodel、flet |
| （组装根） | `cs_music_player/bootstrap.py` | 唯一「认识所有层」的地方，负责 `new` 具体实现并注入 | 全部 |

`main.py` 只负责窗口参数与显示时机，业务装配全部交给 `bootstrap.py`。

### 声明式 UI：UI = f(状态)

- `AppViewModel` 持有**全部**界面状态（曲目列表、当前曲目、播放进度、歌词、主题、桌面歌词配置……），
  派生量（`playing_track` / `filtered_tracks` / `active_lyric_index` …）都是只读 property，不重复存储。
- 视图模型是纯 Python 类（`ObservableModel`），**不导入 flet**，因此可以在无界面环境下被完整单测。
- `view/app.py::PlayerApp` 订阅视图模型的 `notify()`，状态一变就整棵树重渲染；
  组件本身是纯函数式的（props 进、控件出），不持有业务状态（只有「进度条是否正在拖动」这类瞬时 UI 状态）。

### 依赖倒置怎么落地

- 服务层只 `import cs_music_player.infra.ports`，永远看不到 `FletAudioEngine`、`MutagenMetadataReader` 这些具体类。
- 视图模型也不依赖任何服务类：它在 `viewmodel/ports.py` 里声明自己需要的六组能力
  （`PlaybackOps` / `LibraryOps` / `FolderHistoryOps` / `LyricsOps` / `SettingsOps` / `DesktopLyricOps`），
  服务层靠**结构化子类型**满足它们，因此没有人需要反向 import。
- 音频引擎反过来需要观察者（也就是播放服务）才能构造，所以用**工厂函数**注入
  （`PlaybackService(engine_factory, observer)`），两边的构造顺序不再互相牵制。
- 桌面歌词悬浮窗跑在自己的线程上，回调经 `FletLoopDispatcher`（`page.run_task`）投递回 UI 事件循环，
  于是视图模型可以假定自己始终单线程，不需要任何锁。
- 持久化的**键名**属于抽象契约，定义在 `infra/ports.py`（而不是某个适配器里），服务层因此不依赖任何具体实现。

### 架构回归测试

`tests/test_architecture.py` 用 AST 静态校验上述所有约束，并在子进程里验证
「导入 models / service / viewmodel **不会**牵进 flet、Pillow、mutagen」。它同时守住
自己的盲区：包内每个文件都必须落在某一层（新加顶层模块会被判失败）、非字面量的动态导入只允许出现在
包的 `__init__` 里、PEP 562 惰性转出表指向的子模块也必须落在允许范围内。

`tests/test_viewmodel_ports.py` 逐一校验具体服务满足视图模型声明的契约——成员齐全、参数名/种类/默认值一致，
接口一漂移就会失败。

`tests/test_viewmodel.py` 用假基础设施端到端跑通导入、收藏、歌词、主题、悬浮窗、睡眠定时器等全部流程。

### 回归验证方式

重构前后用「真机像素对比」兜底：同一份代码树（`git` HEAD）与重构后的树分别在同样的
启动参数下跑起来，用 `PrintWindow(PW_RENDERFULLCONTENT)`（进程声明 per-monitor-v2 DPI 感知）
抓整窗 2065×1365 位图逐像素比对。覆盖：目录启动、单文件启动（自动播放 + 歌词）、暗色主题、
带持久化收藏/固定文件夹/歌词偏移/字号的启动、以及「目录启动 + 首曲带偏移」。
再用字号、偏移、主题、曲目内容四项灵敏度检查确认这套比对确实覆盖到了歌词面板与播放栏。

## 项目结构

```
cs-music-player/
├── main.py                       # 程序入口：窗口参数、显示时机、预热钩子
├── pyproject.toml                # 项目配置、运行/dev 依赖声明
├── uv.lock                       # uv 锁定依赖版本（提交到版本库）
├── cs_music_player/
│   ├── __init__.py               # 惰性转出的常用名字（Track / PlayMode …）
│   ├── bootstrap.py              # 组装根：基础设施 → 服务 → 视图模型
│   ├── models/                   # ① 模型层
│   │   ├── constants.py          #    格式、字号/行距、速度、调色板、桌面歌词尺寸
│   │   ├── playback.py           #    PlayMode 枚举、PlaybackState
│   │   ├── track.py              #    Track / AudioMetadata / StartupLoad
│   │   ├── lyrics.py             #    LyricLine / LyricsDocument
│   │   └── settings.py           #    ThemeMode、DesktopLyricConfig
│   ├── infra/                    # ② 基础设施层
│   │   ├── ports.py              #    对外抽象接口 + 持久化键名（零第三方依赖）
│   │   ├── audio.py              #    flet-audio 引擎
│   │   ├── metadata.py           #    mutagen 元数据 / 封面
│   │   ├── lyrics_repository.py  #    本地歌词索引与 LRC 解析
│   │   ├── lyrics_provider.py    #    LRCLIB 在线歌词
│   │   ├── preferences.py        #    SharedPreferences 适配器
│   │   ├── picker.py             #    目录选择框
│   │   ├── dispatch.py           #    跨线程回调 → UI 事件循环
│   │   ├── startup_args.py       #    命令行启动路径解析
│   │   └── desktop_lyric/        #    Win32 分层窗口 + Pillow 渲染
│   ├── service/                  # ③ 服务/业务层
│   │   ├── playback.py           #    播放控制与切歌策略
│   │   ├── library.py            #    目录选择/扫描、曲目构建、收藏
│   │   ├── folders.py            #    最近打开与固定的文件夹历史
│   │   ├── lyrics.py             #    歌词读取、按曲目偏移、后台补齐
│   │   ├── settings.py           #    主题 / 字号 / 桌面歌词配置
│   │   ├── desktop_lyric.py      #    悬浮窗编排
│   │   └── sleep.py              #    睡眠倒计时
│   ├── viewmodel/                # ④ 视图模型层
│   │   ├── observable.py         #    极简观察者基类（零依赖）
│   │   ├── ports.py              #    本层需要的抽象接口（依赖倒置的「接口」侧）
│   │   └── app.py                #    AppViewModel：全部 UI 状态与动作
│   └── view/                     # ⑤ 视图层
│       ├── theme.py              #    可切换调色板 + Flet 主题
│       ├── app.py                #    根组件 PlayerApp（工具栏 + 装配）
│       └── components/           #    纯 props 驱动的子组件
├── tests/                        # pytest 单元测试（含架构回归）
└── scripts/
    └── smoke_test.py             # 元数据 / 收藏逻辑的冒烟测试
```

## 技术栈

| 依赖 | 用途 |
|------|------|
| [flet](https://flet.dev/) ≥ 1.0.4 | 声明式 UI 框架（`@ft.component`、`use_state`、`use_effect`） |
| [flet-audio](https://pypi.org/project/flet-audio/) ≥ 1.0.4 | 音频播放 |
| [mutagen](https://pypi.org/project/mutagen/) ≥ 1.47 | 读取时长、标签（歌手/专辑）、采样率/码率、内嵌封面 |
| [Pillow](https://python-pillow.org/) ≥ 10.0 | 桌面歌词悬浮窗的逐帧渲染 |
| [pytest](https://docs.pytest.org/) ≥ 8.0 | 单元测试（dev 组） |

## 开发

### 运行测试

```powershell
uv run python -m pytest
```

覆盖范围：播放模式与切歌策略、音量倍速边界、进度条边界、最近/固定文件夹、主题与字号持久化、
歌词偏移、LRCLIB 匹配与标签解析、歌词版式（中线/行高/窗口）、桌面歌词渲染版式、
睡眠定时器、视图模型端到端流程，以及**分层依赖约束**（AST 静态校验 + 子进程导入验证）。

### 冒烟测试

```powershell
uv run python scripts/smoke_test.py
```

测试元数据读取（需项目根目录存在 `viper.mp3`）与收藏状态切换逻辑。

### 主要模块导出

```python
from cs_music_player import Track, PlayMode, ThemeMode
from cs_music_player.models import SUPPORTED_FORMATS, MODE_SEQUENCE
from cs_music_player.view import palette
```

包级导入是**惰性**的（PEP 562），`import cs_music_player` 本身几乎不花时间。

### 输入框边框（flet 1.x）

`FormFieldControl`（`TextField`、`DropdownM2` 等）的 `border_color`、`border_width`、`border_radius`、
`focused_border_color`、`focused_border_width` 自 flet 1.0 起**已弃用**，1.3.0 移除；统一改用 `border`：

```python
# 全状态同一形状、颜色交给主题按状态解析
ft.TextField(border=ft.OutlineInputBorder(border_radius=8))

# 需要指定各状态颜色时用状态字典（未给 side 的状态回落到 DEFAULT 的 side）
ft.TextField(
    border={
        ft.ControlState.DEFAULT: ft.OutlineInputBorder(
            border_radius=12, side=ft.BorderSide(1, palette.BORDER)
        ),
        ft.ControlState.FOCUSED: ft.OutlineInputBorder(
            border_radius=12, side=ft.BorderSide(2, palette.PRIMARY_LIGHT)
        ),
    }
)
```

边框对象在组件构建时创建，颜色需直接读 `palette.*`（不要提到模块级常量，否则暗色主题切换不会更新）。

### 启动优化（`main.py`）

- `prewarm()` 在「客户端进程刚被拉起」钩子里于后台线程提前导入业务模块并构造一次 `ft.Theme`
  （首次构造要惰性加载 58 个模块，约 96ms）。实测「进程启动 → 窗口可见」0.68s → 0.60s。
- 窗口参数必须在 `before_main`（客户端注册阶段）里设定，否则会「左上角闪一下再跳尺寸」。
- `FLET_APP_HIDDEN` + 同色占位页 + `wait_until_ready_to_show()` 保证窗口首次出现时内容已经画好。

## 许可证

暂未指定。使用前请根据仓库实际情况补充许可信息。