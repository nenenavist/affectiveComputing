import json
from typing import Dict, List
from urllib.parse import urlencode
from urllib.request import urlopen

from app.music.lastfm_client import get_top_tracks_by_tag
from app.schemas import Emotion


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

EMOTION_SEARCH_TERMS: Dict[Emotion, List[str]] = {
    "happy": ["happy pop", "dance pop", "feel good"],
    "sad": ["sad acoustic", "melancholy indie", "sad piano"],
    "angry": ["angry rock", "metal rage", "hard rock"],
    "neutral": ["ambient calm", "instrumental chill", "jazz calm"],
}


EMOTION_TAGS: Dict[Emotion, List[str]] = {
    "happy": ["happy", "dance", "pop", "feel good"],
    "sad": ["sad", "melancholic", "acoustic", "piano"],
    "angry": ["angry", "metal", "hard rock", "rage"],
    "neutral": ["ambient", "calm", "instrumental", "jazz"],
}


def fetch_track_candidates(emotion: Emotion, limit: int = 18) -> List[Dict[str, str]]:
    candidates = []

    for tag in EMOTION_TAGS[emotion][:2]:
        candidates.extend(get_top_tracks_by_tag(tag, limit=limit // 2))

    if len(candidates) < limit:
        for term in EMOTION_SEARCH_TERMS[emotion]:
            candidates.extend(_search_itunes(term, limit=limit // len(EMOTION_SEARCH_TERMS[emotion])))

    return _dedupe_tracks(candidates)[:limit]


def emotion_seed_tags(emotion: Emotion) -> List[str]:
    return EMOTION_TAGS[emotion]


def _search_itunes(term: str, limit: int) -> List[Dict[str, str]]:
    query = urlencode({"term": term, "media": "music", "entity": "song", "limit": str(limit)})

    try:
        with urlopen(f"{ITUNES_SEARCH_URL}?{query}", timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    result = []
    for item in payload.get("results", []):
        title = item.get("trackName")
        artist = item.get("artistName")
        if not title or not artist:
            continue

        result.append(
            {
                "id": f"itunes-{item.get('trackId')}",
                "title": title,
                "artist": artist,
                "duration": _format_duration(int(item.get("trackTimeMillis") or 0)),
                "coverUrl": item.get("artworkUrl100", "").replace("100x100bb", "300x300bb"),
                "spotifyUrl": item.get("trackViewUrl", ""),
                "source": "itunes",
                "genre": item.get("primaryGenreName", ""),
            }
        )

    return result


def _format_duration(duration_ms: int) -> str:
    total_seconds = max(0, duration_ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _dedupe_tracks(tracks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique = []

    for track in tracks:
        key = (track["title"].lower(), track["artist"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(track)

    return unique
