"""选中与播放的同步：切歌只由播放服务驱动，单击只改选中项。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cs_music_player.models import Track

from fakes import make_view_model


def make_tracks(count: int) -> list[Track]:
    return [Track(path=Path(f"{i}.mp3")) for i in range(count)]


def test_track_change_syncs_selection_and_current() -> None:
    vm, _ = make_view_model()
    vm.tracks = make_tracks(3)

    vm.on_track_change(2)

    assert vm.current == 2
    assert vm.selected == 2


def test_play_at_drives_current_through_the_service() -> None:
    vm, _ = make_view_model()
    tracks = make_tracks(3)
    asyncio.run(vm._apply_tracks(tracks))

    asyncio.run(vm.play(tracks[2]))

    # play_at -> on_track_change 回调把 current / selected 一起同步
    assert vm.current == 2
    assert vm.selected == 2
    assert vm.is_playing is True


def test_select_does_not_change_current() -> None:
    vm, _ = make_view_model()
    tracks = make_tracks(3)
    vm.tracks = tracks

    vm.select(tracks[1])

    assert vm.selected == 1
    assert vm.current == -1


def test_import_without_autoplay_resets_current_but_keeps_selection() -> None:
    vm, _ = make_view_model()
    tracks = make_tracks(2)

    asyncio.run(vm._apply_tracks(tracks))

    assert vm.tracks == tracks
    assert vm.current == -1
    assert vm.selected == 0
    assert vm.is_playing is False


def test_display_track_prefers_current_over_selected() -> None:
    vm, _ = make_view_model()
    tracks = make_tracks(3)
    vm.tracks = tracks
    vm.selected = 2
    vm.current = 1

    assert vm.display_track is tracks[1]

    vm.current = -1
    assert vm.display_track is tracks[2]
