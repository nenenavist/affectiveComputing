"""Mood-aligned track provider built on Last.fm tags + iTunes previews.

Architecture:
    1. Pick a weighted mix of Last.fm mood tags from the detected emotions.
    2. Fetch top tracks for those tags in parallel.
    3. For each candidate, look up the same artist/title in iTunes to attach
       a 30-second preview URL, high-res cover art, and duration.
    4. Filter to tracks WITH previews so the UI always has playable audio.

Last.fm tags are *the* alternative to Spotify's deprecated audio-features API:
they are community-driven, cover millions of songs, and require only a free
API key (https://www.last.fm/api/account/create).
"""
from __future__ import annotations

import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.music.lastfm_client import (
    get_top_tracks_for_tags,
    is_configured as lastfm_is_configured,
)
from app.schemas import Emotion


_logger = logging.getLogger(__name__)


# A LARGE pool of Last.fm tags per emotion → more diverse playlists.
EMOTION_TAGS: Dict[Emotion, List[str]] = {
    "happy": [
        "happy", "feel good", "uplifting", "upbeat", "summer", "party",
        "joyful", "energetic", "fun", "sunshine", "dance", "good mood",
        "positive", "indie pop", "euphoric",
    ],
    "sad": [
        "sad", "melancholic", "melancholy", "heartbreak", "sentimental",
        "emotional", "depressing", "tear-jerker", "blue", "nostalgic",
        "introspective", "lonely", "soft", "rainy day", "longing",
    ],
    "angry": [
        "angry", "aggressive", "intense", "rage", "powerful",
        "metalcore", "hard rock", "punk", "metal", "industrial",
        "heavy", "fast", "explosive", "rebellious", "stress relief",
    ],
    "neutral": [
        "chill", "ambient", "relaxing", "calm", "easy listening",
        "background", "lounge", "minimal", "study", "instrumental",
        "lo-fi", "jazz", "chillout", "focus", "soft instrumental",
    ],
}


def tag_to_emotion(tag: str) -> Optional[Emotion]:
    """Map a Last.fm mood tag back to one of our 4 emotion categories."""
    if not tag:
        return None
    tag_lower = tag.strip().lower()
    for emotion, tags in EMOTION_TAGS.items():
        if tag_lower in tags:
            return emotion
    return None


def is_available() -> bool:
    return lastfm_is_configured()


def fetch_mood_tracks(
    emotion_weights: Dict[Emotion, float],
    *,
    desired: int = 30,
) -> List[Dict[str, str]]:
    """Returns up to `desired` tracks aligned with the emotion mix.

    Each track is enriched with a 30-second preview URL + cover image from
    iTunes when available.  Tracks WITHOUT a preview are kept as a back-up
    so the playlist is never empty.
    """
    if not lastfm_is_configured():
        return []

    tag_mix = _build_tag_mix(emotion_weights, total_tags=8)
    if not tag_mix:
        return []

    _logger.info("Last.fm tag mix: %s", tag_mix)
    candidates = get_top_tracks_for_tags(tag_mix, total_limit=80)
    if not candidates:
        return []

    deduped = _dedupe(candidates)
    random.shuffle(deduped)

    # Enrich top candidates with iTunes data (preview + cover + duration).
    enriched: List[Dict[str, str]] = []
    enrich_budget = min(60, len(deduped))

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_enrich_with_itunes, track): track
            for track in deduped[:enrich_budget]
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    enriched.append(result)
            except Exception as error:
                _logger.warning("iTunes enrichment failed: %s", error)

    # Keep originals (without previews) as a fallback if enrichment under-delivered.
    enriched_ids = {t["id"] for t in enriched}
    leftovers = [t for t in deduped if t["id"] not in enriched_ids]
    final_pool = enriched + leftovers

    # Prefer tracks with a preview URL.
    with_preview = [t for t in final_pool if t.get("previewUrl")]
    without_preview = [t for t in final_pool if not t.get("previewUrl")]

    return (with_preview + without_preview)[:desired]


def _build_tag_mix(weights: Dict[Emotion, float], total_tags: int = 8) -> List[str]:
    """Pick mood tags from the dominant emotion(s).

    Rules:
        - If one emotion clearly dominates (≥ 55 % of the weight mass),
          ALL tags come from that emotion's pool. Otherwise the mix would
          confuse the user ("I'm sad, why are there angry tracks?").
        - Two emotions close in weight (e.g. 50/50 happy + sad) →
          tags split proportionally.
        - Sub-25 % emotions are ignored entirely.
    """
    positives = {e: max(weights.get(e, 0.0), 0.0) for e in EMOTION_TAGS}
    total = sum(positives.values())
    if total <= 0:
        positives = {"neutral": 1.0}
        total = 1.0

    shares = {e: positives[e] / total for e in EMOTION_TAGS}
    sorted_emotions = sorted(shares.items(), key=lambda item: item[1], reverse=True)
    dominant_emotion, dominant_share = sorted_emotions[0]

    chosen: List[str] = []

    if dominant_share >= 0.55:
        # Use ONLY the dominant emotion's pool. No mixing.
        pool = list(EMOTION_TAGS[dominant_emotion])
        random.shuffle(pool)
        chosen = pool[:total_tags]
    else:
        # Top 2 emotions split, but only if each ≥ 25 %.
        for emotion, share in sorted_emotions:
            if share < 0.25:
                continue
            slots = max(1, round(share * total_tags))
            pool = list(EMOTION_TAGS[emotion])
            random.shuffle(pool)
            chosen.extend(pool[:slots])
            if len(chosen) >= total_tags:
                break

        if not chosen:
            pool = list(EMOTION_TAGS[dominant_emotion])
            random.shuffle(pool)
            chosen = pool[:total_tags]

    chosen = list(dict.fromkeys(chosen))
    random.shuffle(chosen)
    return chosen[:total_tags]


def _dedupe(tracks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set = set()
    out: List[Dict[str, str]] = []
    for track in tracks:
        key = (track.get("artist", "").strip().lower(), track.get("title", "").strip().lower())
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        out.append(track)
    return out


# ── iTunes enrichment ────────────────────────────────────────────────────────

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def _enrich_with_itunes(track: Dict[str, str]) -> Optional[Dict[str, str]]:
    artist = track.get("artist", "").strip()
    title = track.get("title", "").strip()
    if not artist or not title:
        return None

    params = {
        "term": f"{artist} {title}",
        "entity": "song",
        "media": "music",
        "limit": "5",
    }
    request = Request(
        f"{ITUNES_SEARCH_URL}?{urlencode(params)}",
        headers={
            "User-Agent": "mood-music-machine/2.0",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    results = payload.get("results", []) or []
    if not results:
        return None

    # Find best match: same artist and same title (case-insensitive substring).
    artist_lower = artist.lower()
    title_lower = title.lower()
    match = None
    for item in results:
        item_artist = (item.get("artistName") or "").lower()
        item_title = (item.get("trackName") or "").lower()
        if artist_lower in item_artist and title_lower in item_title:
            match = item
            break
    if match is None:
        match = results[0]

    cover = match.get("artworkUrl100") or ""
    if cover:
        cover = cover.replace("100x100", "600x600")

    duration_ms = int(match.get("trackTimeMillis") or 0)
    minutes, seconds = divmod(max(0, duration_ms // 1000), 60)

    track_url = match.get("trackViewUrl") or ""
    preview = match.get("previewUrl") or None

    return {
        **track,
        "id": str(match.get("trackId") or track.get("id")),
        "coverUrl": cover,
        "duration": f"{minutes}:{seconds:02d}",
        "previewUrl": preview,
        "spotifyUrl": track_url,
        "source": "lastfm+itunes",
    }
