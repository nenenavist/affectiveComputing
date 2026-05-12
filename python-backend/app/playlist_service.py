import logging
import math
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.itunes_service import search_tracks_for_mood as itunes_search_tracks_for_mood
from app.ml import detect_emotion, detect_emotion_weights
from app.schemas import Emotion, EmotionWeights, MoodRequest, Playlist, Track
from app.spotify_service import SpotifyApiError, search_tracks_for_mood as spotify_search_tracks_for_mood


_logger = logging.getLogger(__name__)
MIN_TRACKS_REQUIRED = 5
EMOTIONS: List[Emotion] = ["happy", "sad", "angry", "neutral"]


GENRE_POOLS: Dict[Emotion, List[str]] = {
    "happy": ["pop", "dance", "disco", "funk", "electropop", "indie pop"],
    "sad": ["acoustic", "piano", "indie", "singer-songwriter", "ambient", "lo-fi"],
    "angry": ["rock", "metal", "punk", "hard rock", "alt-rock", "industrial"],
    "neutral": ["chill", "jazz", "ambient", "study", "classical", "lo-fi"],
}

EMOTION_MOOD_TERMS: Dict[Emotion, List[str]] = {
    "happy": ["feel good", "uplifting", "summer hits", "party vibes", "good mood"],
    "sad": ["melancholy", "heartbreak", "rainy day", "soft acoustic", "emotional ballad"],
    "angry": ["heavy energy", "rage", "intense", "powerful riffs", "stress relief"],
    "neutral": ["calm focus", "background music", "lofi study", "easy listening", "minimal"],
}

EMOTION_AUDIO_TARGETS: Dict[Emotion, Dict[str, float]] = {
    "happy": {"valence": 0.82, "energy": 0.72, "tempo": 122.0},
    "sad": {"valence": 0.22, "energy": 0.32, "tempo": 78.0},
    "angry": {"valence": 0.42, "energy": 0.9, "tempo": 142.0},
    "neutral": {"valence": 0.55, "energy": 0.48, "tempo": 100.0},
}

PLAYLIST_NAMES: Dict[Emotion, List[str]] = {
    "happy": ["Светлый импульс", "Тёплый заряд", "Движение вверх"],
    "sad": ["Мягкая глубина", "Тихий вечер", "Спокойная грусть"],
    "angry": ["Выпустить напряжение", "Громкий фокус", "Сильный поток"],
    "neutral": ["Ровный ритм", "Чистый фокус", "Баланс дня"],
}

TRACK_MOOD_KEYWORDS: Dict[Emotion, List[str]] = {
    "happy": [
        "happy",
        "joy",
        "sun",
        "summer",
        "party",
        "dance",
        "good mood",
        "feel good",
        "радост",
        "свет",
        "улыб",
        "празд",
        "весел",
        "тепл",
    ],
    "sad": [
        "sad",
        "melanch",
        "heartbreak",
        "alone",
        "lonely",
        "rain",
        "blue",
        "cry",
        "груст",
        "тоск",
        "дожд",
        "печал",
        "одиноч",
        "слез",
    ],
    "angry": [
        "angry",
        "rage",
        "fury",
        "metal",
        "hard",
        "punk",
        "fight",
        "fire",
        "зл",
        "ярост",
        "гнев",
        "взрыв",
        "жест",
        "бунт",
    ],
    "neutral": [
        "calm",
        "focus",
        "study",
        "ambient",
        "lofi",
        "chill",
        "instrumental",
        "background",
        "спокой",
        "фон",
        "медит",
        "концентр",
        "ровн",
    ],
}

OPPOSITE_EMOTION_KEYWORDS: Dict[Emotion, List[str]] = {
    "happy": TRACK_MOOD_KEYWORDS["sad"] + TRACK_MOOD_KEYWORDS["angry"],
    "sad": TRACK_MOOD_KEYWORDS["happy"],
    "angry": TRACK_MOOD_KEYWORDS["happy"] + TRACK_MOOD_KEYWORDS["neutral"],
    "neutral": TRACK_MOOD_KEYWORDS["angry"],
}


def build_playlist(request: MoodRequest) -> Playlist:
    emotion_weights = detect_emotion_weights(request)
    dominant_emotion = detect_emotion(request)
    audio_targets = _weighted_audio_targets(emotion_weights)
    seed_genres = _pick_seed_genres(emotion_weights)
    queries = _build_search_queries(seed_genres, emotion_weights)
    itunes_queries = _build_itunes_queries(seed_genres, emotion_weights, dominant_emotion)

    raw_tracks: List[Dict[str, str]] = []
    spotify_error: Optional[SpotifyApiError] = None

    try:
        raw_tracks = spotify_search_tracks_for_mood(queries=queries, limit=30)
    except SpotifyApiError as error:
        spotify_error = error
        _logger.warning("Spotify search failed, will try iTunes fallback: %s", error)

    if len(raw_tracks) < MIN_TRACKS_REQUIRED:
        try:
            fallback_tracks = itunes_search_tracks_for_mood(queries=itunes_queries, limit=30)
        except Exception as error:
            _logger.warning("iTunes fallback failed: %s", error)
            fallback_tracks = []

        if fallback_tracks:
            existing_ids = {track["id"] for track in raw_tracks}
            for track in fallback_tracks:
                if track["id"] not in existing_ids:
                    raw_tracks.append(track)

    if len(raw_tracks) < MIN_TRACKS_REQUIRED:
        if spotify_error is not None:
            raise ValueError(_human_spotify_error(spotify_error))
        raise ValueError(
            "Не удалось собрать плейлист: ни Spotify, ни резервный источник iTunes "
            "не вернули достаточно треков. Попробуйте ещё раз или измените настроение."
        )

    ranked_tracks = _rank_tracks(raw_tracks, emotion_weights, seed_genres)
    tracks = [
        Track(
            id=track["id"],
            title=track["title"],
            artist=track["artist"],
            duration=track["duration"],
            coverUrl=track["coverUrl"],
            spotifyUrl=track["spotifyUrl"],
            previewUrl=track.get("previewUrl"),
            source=track.get("source") or "spotify",
            musicEmotion=track.get("musicEmotion"),
            musicEmotionScore=track.get("musicEmotionScore"),
        )
        for track in ranked_tracks[:30]
    ]

    playlist_id = f"mmm-{dominant_emotion}-{uuid4().hex[:12]}"
    playlist_name = f"{random.choice(PLAYLIST_NAMES[dominant_emotion])} #{random.randint(100, 999)}"

    return Playlist(
        id=playlist_id,
        playlistId=playlist_id,
        name=playlist_name,
        emotion=dominant_emotion,
        emotionWeights=emotion_weights,
        spotifyUrl="",
        tracks=tracks,
        audioTargets=audio_targets,
        seedGenres=seed_genres,
    )


def _rank_tracks(
    tracks: List[Dict[str, str]],
    emotion_weights: EmotionWeights,
    seed_genres: List[str],
) -> List[Dict[str, str]]:
    dominant_emotion = max(emotion_weights, key=emotion_weights.get)
    scored_tracks: List[Tuple[float, float, Dict[str, str]]] = []
    seen_ids: set[str] = set()

    for track in tracks:
        track_id = track.get("id")
        if not track_id or track_id in seen_ids:
            continue
        seen_ids.add(track_id)

        score, predicted_emotion, confidence, dominant_probability = _score_track(
            track,
            emotion_weights,
            seed_genres,
        )
        enriched = {
            **track,
            "musicEmotion": predicted_emotion,
            "musicEmotionScore": round(confidence, 4),
        }
        scored_tracks.append((score, dominant_probability, enriched))

    scored_tracks.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2].get("artist", "").lower(),
            item[2].get("title", "").lower(),
            item[2].get("id", ""),
        )
    )

    high_match_tracks: List[Dict[str, str]] = []
    low_match_tracks: List[Dict[str, str]] = []
    for _score, dominant_probability, track in scored_tracks:
        track_emotion = track.get("musicEmotion")
        if track_emotion == dominant_emotion or dominant_probability >= 0.28:
            high_match_tracks.append(track)
        else:
            low_match_tracks.append(track)

    selected: List[Dict[str, str]] = []
    artist_caps = defaultdict(int)
    leftovers: List[Dict[str, str]] = []

    for candidate_pool in (high_match_tracks, low_match_tracks):
        for track in candidate_pool:
            artist_key = track.get("artist", "").strip().lower()
            if artist_key and artist_caps[artist_key] >= 2:
                leftovers.append(track)
                continue
            if _is_near_duplicate(track, selected):
                continue
            selected.append(track)
            if artist_key:
                artist_caps[artist_key] += 1
            if len(selected) >= 30:
                return selected

    for track in leftovers:
        selected.append(track)
        if len(selected) >= 30:
            break

    return selected


def _score_track(
    track: Dict[str, str],
    emotion_weights: EmotionWeights,
    seed_genres: List[str],
) -> Tuple[float, Emotion, float, float]:
    text = f"{track.get('title', '')} {track.get('artist', '')}".lower()
    dominant_emotion = max(emotion_weights, key=emotion_weights.get)
    emotion_raw_scores: Dict[Emotion, float] = {emotion: 0.0 for emotion in EMOTIONS}

    for emotion in EMOTIONS:
        keyword_hits = _keyword_strength(text, TRACK_MOOD_KEYWORDS[emotion])
        emotion_raw_scores[emotion] += keyword_hits * (0.6 + emotion_weights[emotion] * 1.8)

    genre_strength = _keyword_strength(text, [genre.lower() for genre in seed_genres])
    emotion_raw_scores[dominant_emotion] += genre_strength * 0.95

    opposing_strength = _keyword_strength(text, OPPOSITE_EMOTION_KEYWORDS[dominant_emotion])
    emotion_raw_scores[dominant_emotion] -= opposing_strength * 0.9

    predicted_emotion = max(emotion_raw_scores, key=emotion_raw_scores.get)
    probs = _softmax_emotions(emotion_raw_scores)
    confidence = probs[predicted_emotion]

    dominant_probability = probs[dominant_emotion]
    second_probability = sorted(probs.values(), reverse=True)[1]
    alignment_margin = dominant_probability - second_probability
    weighted_agreement = sum(probs[emotion] * emotion_weights[emotion] for emotion in EMOTIONS)

    score = weighted_agreement * 0.92
    score += dominant_probability * 1.35
    score += alignment_margin * 0.55
    score += _quality_bonus(track)

    if predicted_emotion == dominant_emotion:
        score += 0.22 + confidence * 0.45
    else:
        score -= 0.2 * (1.0 - dominant_probability)
        score += confidence * 0.1

    if dominant_probability < 0.22:
        score -= 0.22

    return round(score, 6), predicted_emotion, confidence, dominant_probability


def _softmax_emotions(raw_scores: Dict[Emotion, float]) -> Dict[Emotion, float]:
    shifted = [raw_scores[emotion] / 1.15 for emotion in EMOTIONS]
    peak = max(shifted)
    exps = [math.exp(value - peak) for value in shifted]
    total = sum(exps) or 1.0
    return {emotion: exps[index] / total for index, emotion in enumerate(EMOTIONS)}


def _quality_bonus(track: Dict[str, str]) -> float:
    bonus = 0.0
    if track.get("previewUrl"):
        bonus += 0.26
    if track.get("coverUrl"):
        bonus += 0.08
    if track.get("source") == "spotify":
        bonus += 0.1
    if track.get("source") == "itunes":
        bonus += 0.05

    duration = track.get("duration", "")
    duration_seconds = _parse_duration_seconds(duration)
    if 110 <= duration_seconds <= 360:
        bonus += 0.06
    elif duration_seconds == 0:
        bonus -= 0.03

    return bonus


def _keyword_strength(text: str, keywords: List[str]) -> float:
    strength = 0.0
    for keyword in keywords:
        if keyword and keyword in text:
            strength += 1.0
    return strength


def _parse_duration_seconds(duration: str) -> int:
    try:
        minutes_str, seconds_str = duration.split(":")
        minutes = int(minutes_str)
        seconds = int(seconds_str)
        return minutes * 60 + seconds
    except Exception:
        return 0


def _is_near_duplicate(candidate: Dict[str, str], selected: List[Dict[str, str]]) -> bool:
    candidate_title_tokens = _normalize_title_tokens(candidate.get("title", ""))
    candidate_artist = candidate.get("artist", "").strip().lower()
    candidate_title = candidate.get("title", "").strip().lower()
    if not candidate_title_tokens:
        return False

    for existing in selected:
        existing_artist = existing.get("artist", "").strip().lower()
        if candidate_artist and existing_artist and candidate_artist != existing_artist:
            continue

        existing_title = existing.get("title", "").strip().lower()
        existing_tokens = _normalize_title_tokens(existing_title)
        if not existing_tokens:
            continue

        overlap = len(candidate_title_tokens & existing_tokens)
        union = len(candidate_title_tokens | existing_tokens) or 1
        similarity = overlap / union

        if similarity >= 0.82:
            return True
        if candidate_title in existing_title or existing_title in candidate_title:
            return True

    return False


def _normalize_title_tokens(value: str) -> set[str]:
    normalized = []
    for token in value.lower().replace("-", " ").replace("_", " ").split():
        cleaned = "".join(char for char in token if char.isalnum())
        if not cleaned:
            continue
        if cleaned in {"mix", "version", "edit", "remix", "radio", "live", "single", "feat"}:
            continue
        normalized.append(cleaned)
    return set(normalized)


def _weighted_audio_targets(weights: EmotionWeights) -> Dict[str, float]:
    values = {"valence": 0.0, "energy": 0.0, "tempo": 0.0}

    for emotion, weight in weights.items():
        targets = EMOTION_AUDIO_TARGETS[emotion]
        values["valence"] += weight * targets["valence"]
        values["energy"] += weight * targets["energy"]
        values["tempo"] += weight * targets["tempo"]

    return {
        "valence": round(_clamp_unit(values["valence"]), 3),
        "energy": round(_clamp_unit(values["energy"]), 3),
        "tempo": round(_clamp_tempo(values["tempo"] or 100.0), 1),
    }


def _pick_seed_genres(weights: EmotionWeights) -> List[str]:
    weighted_genres: Dict[str, float] = {}

    for emotion, weight in weights.items():
        if weight <= 0:
            continue

        for index, genre in enumerate(GENRE_POOLS[emotion]):
            position_penalty = max(0.65, 1.0 - index * 0.09)
            weighted_genres[genre] = weighted_genres.get(genre, 0.0) + weight * position_penalty

    if not weighted_genres:
        return GENRE_POOLS["neutral"][:3]

    ranked = sorted(weighted_genres.items(), key=lambda item: (-item[1], item[0]))
    return [genre for genre, _score in ranked[:3]]


def _build_search_queries(seed_genres: List[str], weights: EmotionWeights) -> List[str]:
    dominant_emotions = [emotion for emotion, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True) if weight > 0]
    if not dominant_emotions:
        dominant_emotions = ["neutral"]

    queries: List[str] = []

    for emotion in dominant_emotions[:2]:
        terms = EMOTION_MOOD_TERMS[emotion][:3]
        for genre in seed_genres:
            for term in terms[:2]:
                queries.append(f"{genre} {term}")
                queries.append(f"{term} {genre}")
        queries.extend(terms[:3])

    queries.extend(seed_genres)
    deduped: List[str] = []
    seen: set[str] = set()

    for query in queries:
        if query in seen:
            continue
        seen.add(query)
        deduped.append(query)

    return deduped[:8]


def _build_itunes_queries(
    seed_genres: List[str],
    weights: EmotionWeights,
    dominant_emotion: Emotion,
) -> List[str]:
    """Plain-language queries that iTunes Search handles better than Spotify operators."""

    queries: List[str] = []
    dominant_terms = EMOTION_MOOD_TERMS[dominant_emotion][:3]

    for genre in seed_genres:
        for term in dominant_terms[:2]:
            queries.append(f"{genre} {term}")

    queries.extend(seed_genres)
    queries.extend(dominant_terms[:3])
    queries.append(f"{dominant_emotion} music")
    queries.append(f"top {dominant_emotion} songs")

    other_emotions = [
        emotion
        for emotion, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True)
        if weight > 0 and emotion != dominant_emotion
    ]
    for emotion in other_emotions[:1]:
        queries.extend(EMOTION_MOOD_TERMS[emotion][:2])

    deduped: List[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped[:8]


def _human_spotify_error(error: SpotifyApiError) -> str:
    if error.status_code == 403:
        return (
            "Spotify заблокировал запрос: для приложения требуется аккаунт разработчика с Premium. "
            "Включите Premium на аккаунте, привязанном к Spotify Developer Dashboard."
        )
    if error.status_code in (401, 400):
        return "Spotify token invalid. Проверьте SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET."
    if error.status_code == 404:
        return "Spotify endpoint недоступен для этого приложения."
    if error.status_code == 429:
        return "Spotify временно ограничил частоту запросов. Подождите минуту и попробуйте ещё раз."
    if error.status_code in (503, 504):
        return (
            "Сервер Spotify сейчас не отвечает (таймаут сети). "
            "Проверьте подключение или попробуйте включить VPN и повторить запрос."
        )
    return f"Spotify API недоступен ({error.status_code}): {error.message}"


def _clamp_unit(value: float, minimum: float = 0.05, maximum: float = 0.95) -> float:
    return min(max(value, minimum), maximum)


def _clamp_tempo(value: float, minimum: float = 60.0, maximum: float = 180.0) -> float:
    return min(max(value, minimum), maximum)
