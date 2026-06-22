"""Unit tests for playlist ranking + diversification ordering."""

import random

from app.playlist_service import (
    _diversify_playlist_order,
    _rank_tracks,
    _titles_are_similar,
)


def _track(track_id, title, artist, **extra):
    base = {
        "id": track_id,
        "title": title,
        "artist": artist,
        "duration": "3:30",
        "coverUrl": "http://cover",
        "spotifyUrl": "",
        "previewUrl": "http://preview",
        "source": extra.pop("source", "lastfm+itunes"),
    }
    base.update(extra)
    return base


def test_no_consecutive_near_duplicate_titles():
    random.seed(1)
    tracks = []
    # Two near-duplicate titles by different artists + filler.
    tracks.append(_track("1", "Happy Song", "Artist A"))
    tracks.append(_track("2", "Happy Song (Radio Edit)", "Artist B"))
    for i in range(3, 12):
        tracks.append(_track(str(i), f"Unique Title {i}", f"Artist {i}"))

    ordered = _diversify_playlist_order(tracks)
    for prev, curr in zip(ordered, ordered[1:]):
        assert not _titles_are_similar(prev["title"], curr["title"]), (
            f"consecutive similar titles: {prev['title']} -> {curr['title']}"
        )


def test_no_consecutive_same_artist_when_alternatives_exist():
    random.seed(2)
    tracks = [
        _track("1", "Track One", "Repeat Artist"),
        _track("2", "Track Two", "Repeat Artist"),
        _track("3", "Track Three", "Other A"),
        _track("4", "Track Four", "Other B"),
        _track("5", "Track Five", "Other C"),
        _track("6", "Track Six", "Other D"),
    ]
    ordered = _diversify_playlist_order(tracks)
    for prev, curr in zip(ordered, ordered[1:]):
        assert prev["artist"].lower() != curr["artist"].lower(), (
            f"consecutive same artist: {prev['artist']}"
        )


def test_diversify_preserves_all_tracks():
    random.seed(3)
    tracks = [_track(str(i), f"Title {i}", f"Artist {i}") for i in range(15)]
    ordered = _diversify_playlist_order(tracks)
    assert sorted(t["id"] for t in ordered) == sorted(t["id"] for t in tracks)


def test_rank_caps_artist_to_two():
    random.seed(4)
    emotion_weights = {"happy": 0.7, "sad": 0.1, "angry": 0.1, "neutral": 0.1}
    tracks = []
    # 5 tracks by the same artist; only 2 should be selected.
    for i in range(5):
        tracks.append(_track(f"same-{i}", f"Mono Track Number {i}", "Mono Artist", tag="happy"))
    # More than 30 other unique artists so the playlist fills WITHOUT needing
    # the capped artist's overflow (the cap is soft when the pool is small).
    for i in range(40):
        tracks.append(_track(f"other-{i}", f"Other Song {i}", f"Artist {i}", tag="happy"))

    ranked = _rank_tracks(tracks, emotion_weights, ["pop"], {"valence": 0.8}, {})
    mono_count = sum(1 for t in ranked if t["artist"].lower() == "mono artist")
    assert mono_count <= 2


def test_rank_does_not_use_title_for_mood_badge():
    random.seed(5)
    emotion_weights = {"happy": 0.8, "sad": 0.1, "angry": 0.05, "neutral": 0.05}
    # Title literally says "sad" but the Last.fm tag is happy.
    tracks = [_track("1", "So Sad Tonight", "Artist A", tag="happy")]
    ranked = _rank_tracks(tracks, emotion_weights, ["pop"], {"valence": 0.8}, {})
    assert ranked[0]["musicEmotion"] == "happy"
