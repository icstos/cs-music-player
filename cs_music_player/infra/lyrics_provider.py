"""LRCLIB 在线歌词来源：后台查询并把歌词保存到 ``{音频目录}/lyrics/``。

对外只暴露 :class:`LrclibLyricsProvider`（实现
:class:`cs_music_player.infra.ports.LyricsProviderPort`）。网络细节、节流与
简繁启发式都封在这一层，服务层只看到「给我歌词文件路径」。
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..infra.ports import MetadataPort
from ..models import TagText, Track

__all__ = [
    "LRCLIB_API",
    "LRCLIB_UA",
    "REQUEST_INTERVAL",
    "LrclibLyricsProvider",
    "detect_hanzi_style",
    "pick_best",
    "query_params",
    "record_hanzi_style",
]

LRCLIB_API = "https://lrclib.net/api"
LRCLIB_UA = "CS-Music-Player/1.0 (https://github.com/cs-music-player)"
#: LRCLIB 建议的请求间隔下限（秒）。
REQUEST_INTERVAL = 0.3

#: 简体/繁体特有的常用汉字，用于粗略判断歌词用字风格。
_SIMPLIFIED_ONLY = frozenset(
    "从这们时样来对还说会点么着过风发爱离开间问儿车长东边学书"
    "听见体师应当让动环红绿结给经虽难亲买卖岁进张几画灯连湾单双"
    "头块蓝号龙飞马鸟鱼机觉变关门兴乡战执专传伟伤价优语请认设许论"
    "证评识词误讲计记议译训让买宝剑电饭锅运烦帘历"
)
_TRADITIONAL_ONLY = frozenset(
    "從這們時樣來對還說會點麼著過風發愛離開間問兒車長東邊學書"
    "聽聞見體師應當讓動環紅綠結給經雖難親買賣歲進張幾畫燈連灣單雙"
    "頭塊藍號龍飛馬鳥魚機覺變關門興鄉戰執專傳偉傷價優語請認設許論"
    "證評識詞誤講計記議譯訓讓買寶劍電飯鍋運煩簾歷"
)

JsonGetter = Callable[[str], "dict[str, Any] | list[Any] | None"]


def detect_hanzi_style(text: str) -> str | None:
    """粗略判断文本用字风格：``'simplified'`` / ``'traditional'`` / ``None``。"""
    if not text:
        return None
    simp = sum(1 for ch in text if ch in _SIMPLIFIED_ONLY)
    trad = sum(1 for ch in text if ch in _TRADITIONAL_ONLY)
    if simp > trad:
        return "simplified"
    if trad > simp:
        return "traditional"
    return None


def record_hanzi_style(record: dict[str, Any]) -> str | None:
    """根据记录中的歌词文本判断简繁风格。"""
    for field in ("syncedLyrics", "plainLyrics"):
        style = detect_hanzi_style(record.get(field) or "")
        if style is not None:
            return style
    return None


def pick_best(
    records: list[dict[str, Any]],
    title: str,
    artist: str,
    duration: float = 0.0,
) -> dict[str, Any] | None:
    """从搜索结果中挑选最匹配的歌词记录（优先简体中文）。"""

    def score(rec: dict[str, Any]) -> float:
        name = (rec.get("trackName") or "").strip()
        art = (rec.get("artistName") or "").strip()
        s = 0.0
        if rec.get("instrumental"):
            s -= 3.0
        if rec.get("syncedLyrics"):
            s += 2.0
        if name:
            low, low_title = name.lower(), title.lower()
            if low == low_title:
                s += 3.0
            elif low_title in low or low in low_title:
                s += 1.5
        if artist and art:
            low_a, low_art = art.lower(), artist.lower()
            if low_a == low_art:
                s += 2.0
            elif low_a in low_art or low_art in low_a:
                s += 0.5
        if duration > 0:
            rec_dur = rec.get("duration")
            if isinstance(rec_dur, (int, float)) and abs(float(rec_dur) - duration) <= 2.0:
                s += 2.0
        style = record_hanzi_style(rec)
        if style == "simplified":
            s += 3.0
        elif style == "traditional":
            s -= 2.0
        return s

    return max(records, key=score, default=None)


def query_params(track: Track, tags: TagText | None = None) -> dict[str, str]:
    """把曲目转成 LRCLIB 查询参数（缺什么就不带什么）。

    标题优先取音频标签原文，没有标签才回退到文件名——不少曲目的标签标题
    与文件名并不一致，用标签去检索命中率高得多。
    """
    tags = tags or TagText()
    params: dict[str, str] = {"track_name": tags.title or track.title or track.path.stem}
    if tags.artist:
        params["artist_name"] = tags.artist
    if tags.album:
        params["album_name"] = tags.album
    if 1 <= track.duration <= 3600:
        params["duration"] = str(int(track.duration))
    return params


def _request_json(url: str, *, timeout: float = 15.0) -> dict[str, Any] | list[Any] | None:
    """同步 GET 请求并解析 JSON；404 / 429 / 网络错误返回 ``None``。"""
    request = urllib.request.Request(
        url, headers={"User-Agent": LRCLIB_UA, "Accept": "application/json"}
    )
    for _ in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry = e.headers.get("Retry-After")
                time.sleep(float(retry) if retry else 1.0)
                continue
            return None
        except Exception:
            return None
    return None


class LrclibLyricsProvider:
    """LRCLIB 客户端：串行节流 + 简繁偏好 + 精确匹配优先。

    Args:
        metadata: 读取音频标签（检索用的标题 / 歌手 / 专辑原文）。
        interval: 相邻请求的最小间隔（秒），LRCLIB 建议 200–500ms。
        get_json: 注入点，默认走 ``urllib``；单测可替换为假实现。
    """

    def __init__(
        self,
        metadata: MetadataPort,
        *,
        interval: float = REQUEST_INTERVAL,
        get_json: JsonGetter | None = None,
    ) -> None:
        self._metadata = metadata
        self._interval = interval
        self._get_json: JsonGetter = get_json or _request_json
        self._lock: asyncio.Lock | None = None
        self._last_request_at = 0.0

    # —— 内部 —— #

    def _get_lock(self) -> asyncio.Lock:
        """延迟创建锁，避免在模块导入时绑定事件循环。"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _throttled_get(self, url: str) -> dict[str, Any] | list[Any] | None:
        """按 LRCLIB 要求串行节流请求。"""
        async with self._get_lock():
            remaining = self._interval - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
            result = await asyncio.to_thread(self._get_json, url)
            self._last_request_at = time.monotonic()
            return result

    async def _fetch(self, track: Track) -> dict[str, Any] | None:
        """查询 LRCLIB：优先简体中文，先按签名精确匹配，再回退到搜索。"""
        # mutagen 读标签是同步 IO：放到线程里，别卡住 UI 事件循环
        tags = await asyncio.to_thread(self._metadata.read_tag_text, track.path)
        params = query_params(track, tags)
        get_url = f"{LRCLIB_API}/get?" + urllib.parse.urlencode(params)
        get_data = await self._throttled_get(get_url)
        get_hit = (
            isinstance(get_data, dict)
            and bool(get_data.get("id"))
            and bool(get_data.get("syncedLyrics"))
        )
        if get_hit and record_hanzi_style(get_data) != "traditional":
            return get_data

        search_params = {k: v for k, v in params.items() if k != "duration"}
        search_data = await self._throttled_get(
            f"{LRCLIB_API}/search?" + urllib.parse.urlencode(search_params)
        )
        candidates = list(search_data) if isinstance(search_data, list) else []
        if get_hit:
            candidates.append(get_data)
        if not candidates:
            return None
        try:
            duration = float(params.get("duration", 0.0))
        except ValueError:
            duration = 0.0
        return pick_best(
            candidates,
            params["track_name"],
            params.get("artist_name", ""),
            duration,
        )

    # —— LyricsProviderPort —— #

    async def download(self, track: Track) -> Path | None:
        """下载歌词到 ``{音频目录}/lyrics/{曲名}.lrc``；失败返回 ``None``。"""
        record = await self._fetch(track)
        if not record:
            return None

        lyrics_dir = track.path.parent / "lyrics"
        try:
            lyrics_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        synced = (record.get("syncedLyrics") or "").strip()
        plain = (record.get("plainLyrics") or "").strip()
        if synced:
            target = lyrics_dir / f"{track.path.stem}.lrc"
            content = synced + "\n"
        elif plain:
            target = lyrics_dir / f"{track.path.stem}.txt"
            content = plain + "\n"
        else:
            return None

        try:
            target.write_text(content, encoding="utf-8")
        except OSError:
            return None
        return target
