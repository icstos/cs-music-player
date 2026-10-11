"""音量与倍速：夹紧到合法范围并实时下发到引擎。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cs_music_player.models import (
    SPEED_MAX,
    SPEED_MIN,
    SPEED_PRESETS,
    Track,
)
from cs_music_player.service.playback import PlaybackService

from fakes import RecordingObserver, engine_factory


def make_service() -> tuple[PlaybackService, Any]:
    factory = engine_factory()
    service = PlaybackService(factory, RecordingObserver())
    service.set_tracks([Track(path=Path("a.mp3"))])
    return service, factory.created[0]  # type: ignore[attr-defined]


def test_default_speed_is_normal() -> None:
    service, engine = make_service()
    assert service.speed == 1.0
    assert engine.speed == 1.0


def test_set_speed_reaches_the_engine() -> None:
    service, engine = make_service()
    service.set_speed(1.5)
    assert service.speed == 1.5
    assert engine.speed == 1.5


def test_set_speed_clamps_to_range() -> None:
    service, _ = make_service()
    service.set_speed(99.0)
    assert service.speed == SPEED_MAX
    service.set_speed(0.01)
    assert service.speed == SPEED_MIN


def test_speed_presets_are_within_range() -> None:
    assert all(SPEED_MIN <= rate <= SPEED_MAX for rate in SPEED_PRESETS)
    assert 1.0 in SPEED_PRESETS


def test_volume_is_clamped_and_forwarded() -> None:
    service, engine = make_service()
    service.set_volume(1.4)
    assert service.volume == 1.0
    assert engine.volume == 1.0
    service.set_volume(-0.3)
    assert service.volume == 0.0


def test_initial_volume_and_speed_can_be_configured() -> None:
    factory = engine_factory()
    service = PlaybackService(factory, RecordingObserver(), volume=0.3, speed=2.0)
    assert service.volume == 0.3
    assert service.speed == 2.0


def test_engine_is_disposed_on_shutdown() -> None:
    service, engine = make_service()
    service.shutdown()
    assert engine.disposed is True
