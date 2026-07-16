"""Smoke tests for cover extraction and favorites persistence helpers."""

from __future__ import annotations

from pathlib import Path

from cs_music_player.audio_player import extract_cover_src, load_tracks_from_directory, Track
from cs_music_player.store import apply_favorites, track_key


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    mp3 = root / "viper.mp3"

    if mp3.exists():
        cover = extract_cover_src(mp3)
        print("viper.mp3 cover:", "yes" if cover else "no")
        if cover:
            print("  data-uri prefix:", cover[:40] + "...")
        tracks = load_tracks_from_directory(root)
        print("tracks in root:", len(tracks))
        for track in tracks:
            print(
                " -",
                track.title,
                "cover=",
                bool(track.cover_src),
                "duration=",
                round(track.duration, 1),
            )
    else:
        print("viper.mp3 not found, skipping cover test")

    sample = Path("sample.mp3")
    tracks = [Track(path=sample, title="Sample")]
    favorites = {track_key(sample.resolve())}
    apply_favorites(tracks, favorites)
    assert tracks[0].favorite is True
    apply_favorites(tracks, set())
    assert tracks[0].favorite is False
    print("apply_favorites: ok")


if __name__ == "__main__":
    main()
