"""播放列表：曲目信息悬浮卡、单曲行与侧边栏。"""

from __future__ import annotations

from collections.abc import Callable

from ui import (
    Container,
    Icons,
    ListView,
    Row,
    SegmentedButton,
    SPACE,
    Text,
    ft,
)

from ...models import Track
from .. import tokens as t
from .cover import cover_radius, track_cover
from .format import _fmt, _fmt_bitrate, _fmt_frequency, _fmt_size, _kv

__all__ = ["PlaylistItem", "Sidebar"]

#: 侧栏宽度：336 = 20 × 16.8，落在 4px 网格上；再窄搜索框放不下「搜索歌曲或文件夹」。
SIDEBAR_WIDTH = 336
#: 行内元素间距，跟 4px 网格走。
GAP = SPACE["2"]


# ── 曲目信息悬浮卡 ── #


def _track_info_tooltip(track: Track) -> ft.Tooltip:
    """曲目信息悬浮卡：延迟出现、跟随光标、反色质感卡片。

    用 M3 的 ``INVERSE_SURFACE`` 而不是写死深色：浅色主题下它是深底浅字，
    深色主题下自动变成浅底深字——两种主题里都「浮」在内容之上。
    """
    header = [
        f"♪　{track.title or track.path.name}",
        _kv("歌手", track.artist or "未知"),
    ]
    rows: list[str] = []
    if track.duration > 0:
        rows.append(_kv("时长", _fmt(track.duration)))
    if track.album:
        rows.append(_kv("专辑", track.album))
    size = _fmt_size(track.file_size)
    if size:
        rows.append(_kv("大小", size))
    freq = _fmt_frequency(track.sample_rate)
    if freq:
        rows.append(_kv("采样率", freq))
    bitrate = _fmt_bitrate(track.bitrate)
    if bitrate:
        rows.append(_kv("码率", bitrate))
    if track.channels:
        rows.append(_kv("声道", str(track.channels)))
    if track.audio_format:
        rows.append(_kv("格式", track.audio_format))

    body = "\n".join(header + (["─" * 15, *rows] if rows else []))
    return ft.Tooltip(
        message=body,
        text_style=ft.TextStyle(
            size=11.5,
            height=1.65,
            color=ft.Colors.ON_INVERSE_SURFACE,
            letter_spacing=0.2,
        ),
        text_align=ft.TextAlign.START,
        padding=ft.Padding.symmetric(horizontal=14, vertical=11),
        decoration=ft.BoxDecoration(
            bgcolor=ft.Colors.INVERSE_SURFACE,
            border_radius=ft.BorderRadius.all(10),
            border=ft.Border.all(
                1, ft.Colors.with_opacity(0.16, ft.Colors.ON_INVERSE_SURFACE)
            ),
            shadows=[
                ft.BoxShadow(
                    blur_radius=22,
                    color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                    offset=ft.Offset(0, 6),
                )
            ],
        ),
        size_constraints=ft.BoxConstraints(max_width=340),
        prefer_below=True,
        vertical_offset=10,
        wait_duration=ft.Duration(milliseconds=600),
        exit_duration=ft.Duration(milliseconds=120),
    )


# ── 单曲行 ── #


@ft.component
def PlaylistItem(
    index: int,
    track: Track,
    is_selected: bool,
    is_playing: bool,
    on_select: Callable[[Track], None],
    on_play: Callable[[Track], None],
    on_favorite: Callable[[Track], None],
) -> ft.Control:
    """一行：序号 · 封面 · 标题/歌手 · 时长 · 收藏。

    单击选中、双击播放——与文件管理器一致；选中只改「看哪首」，不打断正在响的
    那首（打断是不可撤销的，而选中随时可以改）。
    """

    def _on_select(e: ft.ControlEvent) -> None:
        on_select(track)

    async def _on_play(e: ft.ControlEvent) -> None:
        await on_play(track)

    async def _on_favorite(e: ft.ControlEvent) -> None:
        await on_favorite(track)

    row = Container(
        content=Row(
            controls=[
                Text(
                    f"{index + 1:02d}",
                    size=12,
                    color=ft.Colors.PRIMARY if is_selected else t.TEXT_SOFT,
                    width=28,
                    text_align=ft.TextAlign.CENTER,
                ),
                # 信息悬浮卡只挂在封面区域：整行悬浮会挡住行本身的点选判读
                Container(
                    content=track_cover(
                        track,
                        size=40,
                        is_current=is_selected,
                        is_playing=is_playing,
                    ),
                    tooltip=_track_info_tooltip(track),
                ),
                ft.Column(
                    [
                        Text(
                            track.title,
                            size=13,
                            weight=ft.FontWeight.W_600
                            if is_selected
                            else ft.FontWeight.W_500,
                            color=t.SELECTED_TEXT if is_selected else t.TEXT,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        Row(
                            controls=[
                                Text(
                                    track.artist or track.path.parent.name,
                                    size=11,
                                    color=t.TEXT_SOFT,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                Text(
                                    _fmt(track.duration),
                                    size=11,
                                    color=t.TEXT_SOFT,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                            ],
                            spacing=GAP,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=Icons.FAVORITE if track.favorite else Icons.FAVORITE_BORDER,
                    icon_color=ft.Colors.TERTIARY
                    if track.favorite
                    else t.TEXT_SOFT,
                    icon_size=18,
                    tooltip="取消收藏" if track.favorite else "收藏",
                    on_click=_on_favorite,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.all(4),
                        overlay_color=ft.Colors.with_opacity(
                            0.08, ft.Colors.PRIMARY
                        ),
                    ),
                ),
            ],
            spacing=GAP,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=t.SELECTED_BG if is_selected else ft.Colors.TRANSPARENT,
        # 选中态靠一条主色竖线立住，不靠整行反色——列表要能一直扫读
        border=ft.Border(
            left=ft.BorderSide(
                3, ft.Colors.PRIMARY if is_selected else ft.Colors.TRANSPARENT
            ),
        ),
        padding=ft.Padding.only(left=8, right=8, top=6, bottom=6),
        ink=True,
    )

    return ft.GestureDetector(
        on_tap=_on_select,
        on_double_tap=_on_play,
        content=row,
    )


# ── 侧边栏 ── #


@ft.component
def Sidebar(
    tracks: list[Track],
    selected: int,
    playing_track: Track | None,
    search: str,
    show_favorites: bool,
    total_count: int,
    on_search: Callable[[str], None],
    on_toggle_favorites: Callable[[bool], None],
    on_select: Callable[[Track], None],
    on_play: Callable[[Track], None],
    on_favorite: Callable[[Track], None],
    is_playing: bool,
    on_search_focus: Callable[[], None],
    on_search_blur: Callable[[], None],
) -> ft.Control:
    """音乐库侧栏：标题与计数、搜索、全部/收藏、曲目列表。

    标题行给「库里有多少 / 一共多少」两个数——筛选之后「只剩 3 首」和「库里只有
    3 首」是两件事，一个分母就能区分。
    """
    selected_track = tracks[selected] if 0 <= selected < len(tracks) else None

    header = Container(
        content=ft.Column(
            controls=[
                Row(
                    controls=[
                        Text(
                            "音乐库",
                            size=16,
                            weight=ft.FontWeight.W_700,
                            color=t.TEXT,
                        ),
                        Container(expand=True),
                        Text(
                            f"{len(tracks)} / {total_count} 首",
                            size=11,
                            color=t.TEXT_SOFT,
                        ),
                    ],
                    spacing=GAP,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.TextField(
                    value=search,
                    on_change=lambda e: on_search(str(e.control.value or "")),
                    on_focus=lambda e: on_search_focus(),
                    on_blur=lambda e: on_search_blur(),
                    hint_text="搜索歌曲或文件夹",
                    prefix_icon=Icons.SEARCH,
                    dense=True,
                    border_radius=12,
                ),
                SegmentedButton(
                    options=["全部", "收藏"],
                    selected=["收藏" if show_favorites else "全部"],
                    allow_empty_selection=False,
                    show_selected_icon=False,
                    on_change=lambda e: on_toggle_favorites(
                        "收藏" in list(e.control.selected or [])
                    ),
                ),
            ],
            spacing=SPACE["3"],
        ),
        padding=ft.Padding.only(
            left=SPACE["4"], right=SPACE["4"], top=SPACE["4"], bottom=SPACE["3"]
        ),
        border=ft.Border(bottom=ft.BorderSide(1, t.LINE)),
    )

    if not tracks:
        body: ft.Control = Container(
            content=ft.Column(
                controls=[
                    ft.Icon(Icons.LIBRARY_MUSIC_OUTLINED, size=44, color=t.TEXT_SOFT),
                    Text(
                        "还没有歌曲",
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=t.TEXT,
                    ),
                    Text(
                        "点右上角「导入音乐」选择文件夹",
                        size=12,
                        color=t.TEXT_SOFT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
    else:
        body = ListView(
            controls=[
                PlaylistItem(
                    i,
                    track,
                    track is selected_track,
                    is_playing and track is playing_track,
                    on_select,
                    on_play,
                    on_favorite,
                )
                for i, track in enumerate(tracks)
            ],
            spacing=2,
            padding=ft.Padding.symmetric(vertical=SPACE["2"]),
            expand=True,
        )

    return Container(
        content=ft.Column(controls=[header, body], spacing=0, expand=True),
        width=SIDEBAR_WIDTH,
        bgcolor=t.PANEL,
        border=ft.Border(right=ft.BorderSide(1, t.LINE)),
    )
