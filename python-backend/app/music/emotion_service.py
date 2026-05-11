from typing import Iterable, Optional

from app.music.feature_extractor import extract_music_features, normalize_tags
from app.music.lastfm_client import get_track_tags
from app.music.emotion_model import get_music_emotion_model
from app.schemas import MusicEmotionResponse


def analyze_music_emotion(
    title: str,
    artist: str,
    tags: Optional[Iterable[str]] = None,
) -> MusicEmotionResponse:
    source = "provided-tags"
    resolved_tags = normalize_tags(tags or [])

    if not resolved_tags:
        resolved_tags = get_track_tags(artist=artist, title=title)
        source = "lastfm" if resolved_tags else "fallback"

    features = extract_music_features(title=title, artist=artist, tags=resolved_tags)
    emotion, score = get_music_emotion_model().predict(features)

    return MusicEmotionResponse(
        emotion=emotion,
        score=score,
        tags=resolved_tags,
        source=source,
    )
