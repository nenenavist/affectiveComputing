"""Last.fm Web API client.

Last.fm exposes COMMUNITY-DRIVEN MOOD TAGS for millions of tracks, which is
the closest realistic alternative to Spotify's audio-features endpoint that
remains free and unrestricted.

API docs: https://www.last.fm/api
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
REQUEST_TIMEOUT = 8
RETRY_ATTEMPTS = 2

_logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(os.getenv("LASTFM_API_KEY"))


def _call(params: Dict[str, str]) -> Optional[Dict]:
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return None

    params.setdefault("api_key", api_key)
    params.setdefault("format", "json")

    request = Request(
        f"{LASTFM_API_URL}?{urlencode(params)}",
        headers={"User-Agent": "mood-music-machine/2.0 (+https://localhost)"},
    )

    last_error: Optional[BaseException] = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            _logger.warning("Last.fm HTTP %s for %s", error.code, params.get("method"))
            return None
        except Exception as error:
            last_error = error
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(0.4 * (attempt + 1))

    _logger.warning("Last.fm request failed: %s", last_error)
    return None


def get_track_tags(artist: str, title: str) -> List[str]:
    payload = _call({
        "method": "track.gettoptags",
        "artist": artist,
        "track": title,
        "autocorrect": "1",
    })
    if not payload:
        return []

    tags_payload = payload.get("toptags", {}).get("tag", [])
    if isinstance(tags_payload, dict):
        tags_payload = [tags_payload]

    return [
        tag["name"].lower()
        for tag in tags_payload[:12]
        if isinstance(tag, dict) and tag.get("name")
    ]


def get_top_tracks_by_tag(tag: str, limit: int = 30, page: int = 1) -> List[Dict[str, str]]:
    """Top tracks for a Last.fm tag (e.g. "happy", "melancholic")."""
    payload = _call({
        "method": "tag.gettoptracks",
        "tag": tag.lower().strip(),
        "limit": str(max(1, min(limit, 50))),
        "page": str(max(1, page)),
    })
    if not payload:
        return []

    tracks_payload = payload.get("tracks", {}).get("track", [])
    if isinstance(tracks_payload, dict):
        tracks_payload = [tracks_payload]

    out: List[Dict[str, str]] = []
    for index, track in enumerate(tracks_payload):
        if not isinstance(track, dict):
            continue
        artist = track.get("artist", {})
        artist_name = artist.get("name") if isinstance(artist, dict) else None
        title = track.get("name")
        if not title or not artist_name:
            continue

        out.append({
            "id": track.get("mbid") or f"lastfm-{tag}-{page}-{index}",
            "title": str(title),
            "artist": str(artist_name),
            "duration": "0:00",
            "coverUrl": "",
            "spotifyUrl": "",
            "previewUrl": None,
            "source": "lastfm",
            "tag": tag,
        })

    return out


def get_top_tracks_for_tags(tags: List[str], total_limit: int = 60) -> List[Dict[str, str]]:
    """Fetch top tracks for several tags in parallel and merge into one pool."""
    tags = [t for t in tags if t and t.strip()]
    if not tags:
        return []

    per_tag_limit = max(8, total_limit // len(tags) + 4)

    pool_tracks: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(len(tags), 6)) as pool:
        # Add a small random page (1 or 2) per tag so consecutive requests
        # return different songs even for the same tag.
        futures = {
            pool.submit(get_top_tracks_by_tag, tag, per_tag_limit, random.choice([1, 2])): tag
            for tag in tags
        }
        for future in as_completed(futures):
            try:
                pool_tracks.extend(future.result())
            except Exception as error:
                _logger.warning("Last.fm tag fetch failed: %s", error)

    return pool_tracks

