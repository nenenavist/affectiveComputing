import json
import os
from typing import List
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
