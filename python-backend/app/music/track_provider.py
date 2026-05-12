from typing import Dict, List

from app.music.lastfm_client import get_top_tracks_by_tag
from app.schemas import Emotion


EMOTION_TAGS: Dict[Emotion, List[str]] = {
    "happy": ["happy", "dance", "pop", "feel good"],
    "sad": ["sad", "melancholic", "acoustic", "piano"],
    "angry": ["angry", "metal", "hard rock", "rage"],
    "neutral": ["ambient", "calm", "instrumental", "jazz"],
}


def fetch_track_candidates(emotion: Emotion, limit: int = 18) -> List[Dict[str, str]]:
    candidates = []

    for tag in EMOTION_TAGS[emotion]:
        candidates.extend(get_top_tracks_by_tag(tag, limit=max(1, limit // len(EMOTION_TAGS[emotion]))))

    return _dedupe_tracks(candidates)[:limit]


def emotion_seed_tags(emotion: Emotion) -> List[str]:
    return EMOTION_TAGS[emotion]


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
