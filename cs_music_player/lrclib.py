"""LRCLIB 歌词下载：播放时后台查询歌词并保存到 {音频目录}/lyrics/。"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .audio_player import Track

LRCLIB_API = "https://lrclib.net/api"
LRCLIB_UA = "CS-Music-Player/1.0 (https://github.com/cs-music-player)"
REQUEST_INTERVAL = 0.3  # LRCLIB 建议请求间隔 200–500ms

_last_request_at = 0.0

# 简体/繁体特有的常用汉字，用于粗略判断歌词用字风格。
# _SIMPLIFIED_ONLY：只出现在简体文中的字形；_TRADITIONAL_ONLY：只出现在繁体文中的对应字形。
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


def _acquire_lock() -> asyncio.Lock:
    """延迟创建全局请求锁，避免在模块导入时绑定事件循环。"""
    if not hasattr(_acquire_lock, "lock"):
        _acquire_lock.lock = asyncio.Lock()
    return _acquire_lock.lock


def _tag_value(tags, *keys: str) -> str:
    """从 mutagen 标签对象中按候选 key 提取首个非空文本。"""
    if not tags:
        return ""
    for key in keys:
        value = tags.get(key)
        if value is None:
            continue
        raw = value.text if hasattr(value, "text") else value
        parts = raw if isinstance(raw, list) else [raw]
        for part in parts:
            text = str(part).strip()
            if text:
                return text
    return ""


def read_metadata(path: Path) -> tuple[str, str, str]:
    """读取音频标签 (artist, title, album)，缺失时返回空串。"""
    try:
        from mutagen import File

        audio = File(str(path))
        if audio is None or audio.tags is None:
            return "", "", ""
        tags = audio.tags
        return (
            _tag_value(tags, "TPE1", "artist", "\xa9ART", "ARTIST"),
            _tag_value(tags, "TIT2", "title", "\xa9nam", "TITLE"),
            _tag_value(tags, "TALB", "album", "\xa9alb", "ALBUM"),
        )
    except Exception:
        return "", "", ""


def _request_json(url: str) -> dict | list | None:
    """同步 GET 请求并解析 JSON；404/429/网络错误返回 None。"""
    request = urllib.request.Request(
        url, headers={"User-Agent": LRCLIB_UA, "Accept": "application/json"}
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=15) as resp:
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


async def _throttled_request(url: str) -> dict | list | None:
    """按 LRCLIB 要求串行节流请求（全局 300ms 间隔）。"""
    global _last_request_at
    lock = _acquire_lock()
    async with lock:
        remaining = REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
        if remaining > 0:
            await asyncio.sleep(remaining)
        result = await asyncio.to_thread(_request_json, url)
        _last_request_at = time.monotonic()
        return result


def detect_hanzi_style(text: str) -> str | None:
    """粗略判断文本用字风格：'simplified' / 'traditional' / None（无法判断）。"""
    if not text:
        return None
    simp = sum(1 for ch in text if ch in _SIMPLIFIED_ONLY)
    trad = sum(1 for ch in text if ch in _TRADITIONAL_ONLY)
    if simp > trad:
        return "simplified"
    if trad > simp:
        return "traditional"
    return None


def record_hanzi_style(record: dict) -> str | None:
    """根据记录中的歌词文本判断简繁风格。"""
    for field in ("syncedLyrics", "plainLyrics"):
        style = detect_hanzi_style(record.get(field) or "")
        if style is not None:
            return style
    return None


def pick_best(
    records: list[dict],
    title: str,
    artist: str,
    duration: float = 0.0,
) -> dict | None:
    """从搜索结果中挑选最匹配的歌词记录（优先简体中文）。"""

    def score(rec: dict) -> float:
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


def _query_params(track: Track) -> dict[str, str]:
    artist, title, album = read_metadata(track.path)
    params: dict[str, str] = {"track_name": title or track.title}
    if artist:
        params["artist_name"] = artist
    if album:
        params["album_name"] = album
    if 1 <= track.duration <= 3600:
        params["duration"] = str(int(track.duration))
    return params


async def fetch_lyrics(track: Track) -> dict | None:
    """查询 LRCLIB：优先简体中文，先按签名精确匹配，再回退到搜索。"""
    params = _query_params(track)
    get_url = f"{LRCLIB_API}/get?" + urllib.parse.urlencode(params)
    get_data = await _throttled_request(get_url)
    get_hit = (
        isinstance(get_data, dict)
        and get_data.get("id")
        and bool(get_data.get("syncedLyrics"))
    )
    if get_hit and record_hanzi_style(get_data) != "traditional":
        return get_data

    search_params = {k: v for k, v in params.items() if k != "duration"}
    search_data = await _throttled_request(
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


async def download_lyrics(track: Track) -> Path | None:
    """下载歌词到 {音频目录}/lyrics/{曲名}.lrc，返回路径；失败返回 None。"""
    record = await fetch_lyrics(track)
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