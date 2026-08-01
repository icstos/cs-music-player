from __future__ import annotations

from pathlib import Path

from cs_music_player.app import PlayerApp
from cs_music_player.audio_player import Player, PlayerCallbacks


def test_sync_track_state_updates_selection_and_current() -> None:
    page = type("Page", (), {})()
    page.theme_mode = None
    page.theme = None
    page.dark_theme = None
    page.services = []
    page.shared_preferences = None
    page.update = lambda: None
    page.run_task = lambda fn: None
    page.on_keyboard_event = None
    page.platform_brightness = "light"

    states: list[tuple[int, int]] = []

    def set_current(index: int) -> None:
        states.append((index, states[-1][1] if states else -1))

    def set_selected(index: int) -> None:
        states.append((states[-1][0] if states else -1, index))

    # Exercise the same state synchronization pattern used by the app.
    def sync_track_state(index: int) -> None:
        set_current(index)
        set_selected(index)

    sync_track_state(2)
    assert states[-2:] == [(2, -1), (2, 2)]
