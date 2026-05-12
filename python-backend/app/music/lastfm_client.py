import json
import os
from typing import Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen


LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"


def get_track_tags(artist: str, title: str) -> List[str]:
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []

    query = urlencode(
        {
            "method": "track.gettoptags",
            "artist": artist,
            "track": title,
            "api_key": api_key,
            "format": "json",
            "autocorrect": "1",
        }
    )

    try:
        with urlopen(f"{LASTFM_API_URL}?{query}", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    tags = payload.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]

    result = []
    for tag in tags[:12]:
        name = tag.get("name") if isinstance(tag, dict) else None
        if name:
            result.append(name.lower())

    return result


def get_top_tracks_by_tag(tag: str, limit: int = 12) -> List[Dict[str, str]]:
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []

    query = urlencode(
        {
            "method": "tag.gettoptracks",
            "tag": tag,
            "api_key": api_key,
            "format": "json",
            "limit": str(limit),
        }
    )

    try:
        with urlopen(f"{LASTFM_API_URL}?{query}", timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    tracks = payload.get("tracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    result = []
    for index, track in enumerate(tracks):
        artist = track.get("artist", {})
        artist_name = artist.get("name") if isinstance(artist, dict) else ""
        title = track.get("name", "")

        if title and artist_name:
            result.append(
                {
                    "id": track.get("mbid") or f"lastfm-{tag}-{index}",
                    "title": title,
                    "artist": artist_name,
                    "duration": "0:00",
                    "coverUrl": "",
                    "source": "lastfm",
                }
            )

    return result
