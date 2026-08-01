from __future__ import annotations

from cs_music_player.ui import _clamp_progress_value


def test_clamp_progress_value_caps_to_slider_range() -> None:
    assert _clamp_progress_value(1.004739336492891, 1.0) == 1.0
    assert _clamp_progress_value(-0.2, 1.0) == 0.0
    assert _clamp_progress_value(0.5, 1.0) == 0.5
    assert _clamp_progress_value(10.0, 20.0) == 0.5
