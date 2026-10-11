"""播放服务的流程：装载、暂停切换、自然播完后的自动切歌。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from cs_music_player.models import MODE_SEQUENCE, Track
from cs_music_player.service.playback import PlaybackService

from fakes import RecordingObserver, engine_factory


def make_tracks(count: int, *, duration: float = 123.0) -> list[Track]:
    return [Track(path=Path(f"{i}.mp3"), duration=duration) for i in range(count)]


def make_service(count: int = 3) -> tuple[PlaybackService, RecordingObserver, Any]:
    factory = engine_factory()
    observer = RecordingObserver()
    service = PlaybackService(factory, observer)
    service.set_tracks(make_tracks(count))
    return service, observer, factory.created[0]  # type: ignore[attr-defined]


def test_play_at_loads_track_and_reports_duration_and_position() -> None:
    service, observer, engine = make_service()

    asyncio.run(service.play_at(1))

    assert service.current == 1
    assert engine.loads == [Path("1.mp3")]
    assert ("duration", 123.0) in observer.events
    assert ("position", 0.0) in observer.events
    assert observer.events[-1] == ("track", 1)


def test_play_at_out_of_range_keeps_state_untouched() -> None:
    service, _, engine = make_service()
    service.set_tracks([])

    asyncio.run(service.play_at(0))

    assert service.current == -1
    assert engine.loads == []


def test_toggle_without_loaded_audio_is_a_noop() -> None:
    """回归：导入列表但尚未选曲时 ``current`` 已是 0、引擎里却没有音频，
    此时播放键在主界面处于禁用态，``toggle`` 不应凭空起播。"""
    service, _, engine = make_service()

    asyncio.run(service.toggle())

    assert engine.loads == []


def test_toggle_pauses_while_playing_and_resumes_afterwards() -> None:
    service, _, engine = make_service()
    asyncio.run(service.play_at(0))
    assert engine.playing is True

    asyncio.run(service.toggle())
    assert engine.pauses == [True]

    asyncio.run(service.toggle())
    assert engine.pauses == [True, False]


def test_completed_advances_to_the_next_track() -> None:
    service, _, engine = make_service()

    async def flow() -> None:
        await service.play_at(0)
        service.on_completed()
        await asyncio.sleep(0)  # 让 create_task 排到的事件真正执行

    asyncio.run(flow())

    assert service.current == 1
    assert engine.loads == [Path("0.mp3"), Path("1.mp3")]


def test_completed_at_the_end_reports_stopped() -> None:
    service, observer, engine = make_service(1)

    async def flow() -> None:
        await service.play_at(0)
        service.on_completed()
        await asyncio.sleep(0)

    asyncio.run(flow())

    assert service.current == 0
    assert engine.loads == [Path("0.mp3")]
    assert observer.events[-1] == ("playing", False)
    assert service.mode == MODE_SEQUENCE


def test_seek_is_forwarded_to_the_engine() -> None:
    service, _, engine = make_service()

    asyncio.run(service.seek(42.5))

    assert engine.seeks == [42.5]


def test_prev_cycles_in_sequence_mode() -> None:
    service, _, engine = make_service()
    asyncio.run(service.play_at(0))
    asyncio.run(service.prev())

    assert service.current == 2
    assert engine.loads[-1] == Path("2.mp3")
