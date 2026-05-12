import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.itunes_service import search_tracks_for_mood as itunes_search_tracks_for_mood
from app.ml import detect_emotion, detect_emotion_weights
from app.music.track_provider import (
    fetch_mood_tracks as lastfm_fetch_mood_tracks,
    is_available as lastfm_is_available,
    tag_to_emotion,
)
from app.schemas import Emotion, EmotionWeights, MoodRequest, Playlist, Track
from app.spotify_service import (
    SpotifyApiError,
    get_audio_features,
    get_recommendations,
    search_tracks_for_mood as spotify_search_tracks_for_mood,
)


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
    "happy": [
        "feel good", "uplifting", "summer hits", "party vibes", "good mood",
        "happy pop", "sunshine", "dance hits", "euphoric", "energetic pop",
        "celebration", "carefree", "tropical pop", "indie joy",
    ],
    "sad": [
        "melancholy", "heartbreak", "rainy day", "soft acoustic", "emotional ballad",
        "late night feels", "introspective", "longing", "bittersweet",
        "cinematic strings", "lonely night", "tender piano", "yearning",
    ],
    "angry": [
        "heavy energy", "rage", "intense", "powerful riffs", "stress relief",
        "headbang", "aggressive metal", "punk fury", "hard hitting",
        "high energy rock", "industrial heavy", "adrenaline workout",
    ],
    "neutral": [
        "calm focus", "background music", "lofi study", "easy listening", "minimal",
        "deep work", "ambient flow", "chill instrumental", "soft jazz",
        "study beats", "coffee shop", "neutral mood", "relax beats",
    ],
}

EMOTION_AUDIO_TARGETS: Dict[Emotion, Dict[str, float]] = {
    "happy": {
        "valence": 0.82, "energy": 0.72, "tempo": 122.0,
        "danceability": 0.7, "acousticness": 0.2,
    },
    "sad": {
        "valence": 0.22, "energy": 0.32, "tempo": 78.0,
        "danceability": 0.4, "acousticness": 0.6,
    },
    "angry": {
        "valence": 0.42, "energy": 0.9, "tempo": 142.0,
        "danceability": 0.55, "acousticness": 0.1,
    },
    "neutral": {
        "valence": 0.55, "energy": 0.48, "tempo": 100.0,
        "danceability": 0.5, "acousticness": 0.45,
    },
}

PLAYLIST_NAMES: Dict[Emotion, List[str]] = {
    "happy": ["Светлый импульс", "Тёплый заряд", "Движение вверх"],
    "sad": ["Мягкая глубина", "Тихий вечер", "Спокойная грусть"],
    "angry": ["Выпустить напряжение", "Громкий фокус", "Сильный поток"],
    "neutral": ["Ровный ритм", "Чистый фокус", "Баланс дня"],
}



def build_playlist(request: MoodRequest) -> Playlist:
    emotion_weights = detect_emotion_weights(request)
    dominant_emotion = detect_emotion(request)
    audio_targets = _weighted_audio_targets(emotion_weights)
    seed_genres = _pick_seed_genres(emotion_weights)

    raw_tracks: List[Dict[str, str]] = []
    audio_features: Dict[str, Dict[str, float]] = {}
    spotify_error: Optional[SpotifyApiError] = None

    # ── PRIMARY: Last.fm community mood tags + iTunes previews ───────────────
    # Last.fm tags ("happy", "melancholic", "energetic", "chill" …) are the
    # closest free alternative to Spotify's deprecated audio-features endpoint:
    # they reflect how millions of real listeners describe each song's mood.
    if lastfm_is_available():
        try:
            raw_tracks = lastfm_fetch_mood_tracks(emotion_weights, desired=40)
            _logger.info(
                "Last.fm + iTunes returned %d mood-tagged tracks for %s.",
                len(raw_tracks), dominant_emotion,
            )
        except Exception as error:
            _logger.warning("Last.fm/iTunes mood fetch failed: %s", error)
    else:
        _logger.info(
            "LASTFM_API_KEY is not set — skipping primary mood-tag path. "
            "Get a free key at https://www.last.fm/api/account/create for "
            "high-quality mood-based track selection."
        )

    # ── FALLBACK 1: Spotify /recommendations (only if not yet disabled) ──────
    if len(raw_tracks) < MIN_TRACKS_REQUIRED:
        try:
            randomised_targets = _randomise_audio_targets(audio_targets)
            spotify_tracks = get_recommendations(
                seed_genres=seed_genres,
                audio_targets=randomised_targets,
                limit=40,
            )
            existing_ids = {t["id"] for t in raw_tracks}
            raw_tracks.extend(t for t in spotify_tracks if t["id"] not in existing_ids)
        except SpotifyApiError as error:
            spotify_error = error
            _logger.warning("Spotify /recommendations unavailable: %s", error)

    # ── FALLBACK 2: Spotify /search if everything else failed ────────────────
    if len(raw_tracks) < MIN_TRACKS_REQUIRED:
        try:
            queries = _build_search_queries(seed_genres, emotion_weights)
            search_tracks = spotify_search_tracks_for_mood(queries=queries, limit=30)
            existing_ids = {t["id"] for t in raw_tracks}
            raw_tracks.extend(t for t in search_tracks if t["id"] not in existing_ids)
        except SpotifyApiError as error:
            if spotify_error is None:
                spotify_error = error
            _logger.warning("Spotify /search fallback failed: %s", error)

    # ── FALLBACK 3: iTunes search directly ───────────────────────────────────
    if len(raw_tracks) < MIN_TRACKS_REQUIRED:
        itunes_queries = _build_itunes_queries(seed_genres, emotion_weights, dominant_emotion)
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

    # Enrich Spotify tracks with audio-features so we can sort by similarity
    # to the target valence/energy/tempo even when /recommendations was used
    # (Spotify's recommendation engine already selects close matches, but the
    # exact ordering it returns is somewhat arbitrary).
    spotify_ids = [t["id"] for t in raw_tracks if t.get("source") == "spotify"]
    if spotify_ids:
        try:
            audio_features = get_audio_features(spotify_ids)
            _logger.info(
                "Audio-features: %d/%d Spotify tracks enriched.",
                len(audio_features), len(spotify_ids),
            )
            if not audio_features:
                _logger.warning(
                    "Spotify /audio-features returned no data — "
                    "likely deprecated for this Developer App. "
                    "Falling back to title-based mood classification for badges."
                )
        except Exception as error:
            _logger.warning("Audio-features fetch failed: %s", error)

    ranked_tracks = _rank_tracks(raw_tracks, emotion_weights, seed_genres, audio_targets, audio_features)
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
    audio_targets: Dict[str, float],
    audio_features: Dict[str, Dict[str, float]],
) -> List[Dict[str, str]]:
    """Rank tracks by AUDIO similarity to the target mood profile.

    Strategy:
        1. If we have audio_features for a track (Spotify only), compute a
           similarity score against the target valence / energy / tempo /
           danceability.  Tracks closer to the target rank higher.
        2. Tracks without audio_features (iTunes, missing data) get a neutral
           score and are randomised among themselves.
        3. Apply quality bonus + soft opposite-keyword penalty (e.g. avoid a
           track named "Sad" in a happy playlist as last-resort heuristic).
        4. Cap by artist (≤ 2) and remove near-duplicate titles.
    """
    dominant_emotion = max(emotion_weights, key=emotion_weights.get)

    scored: List[Tuple[float, Dict[str, str]]] = []
    seen_ids: set[str] = set()

    for track in tracks:
        track_id = track.get("id")
        if not track_id or track_id in seen_ids:
            continue
        seen_ids.add(track_id)

        features = audio_features.get(track_id)
        audio_sim = _audio_similarity(features, audio_targets) if features else None

        if audio_sim is None:
            base_score = 0.6 + random.uniform(-0.05, 0.05)
        else:
            base_score = audio_sim

        base_score += _quality_bonus(track) * 0.35

        # ── Determine display badge ──────────────────────────────────────
        # IMPORTANT: We DO NOT read the track's title to guess its mood.
        # The badge comes from one of two reliable sources, in order:
        #   1. Spotify audio-features (if available)
        #   2. Last.fm community mood tag that brought this track in
        # If neither is available (rare), we just label the track with the
        # user's dominant emotion (the playlist was assembled for them).
        if features:
            predicted_emotion = _emotion_from_features(features)
            confidence = audio_sim if audio_sim is not None else 0.6
        elif track.get("tag"):
            tag_emotion = tag_to_emotion(track["tag"])
            if tag_emotion:
                predicted_emotion = tag_emotion
                if tag_emotion == dominant_emotion:
                    confidence = 0.78 + random.uniform(-0.06, 0.08)
                else:
                    confidence = 0.62 + random.uniform(-0.06, 0.06)
            else:
                predicted_emotion = dominant_emotion
                confidence = 0.6 + random.uniform(-0.04, 0.06)
        else:
            predicted_emotion = dominant_emotion
            confidence = 0.6 + random.uniform(-0.04, 0.06)

        enriched = {
            **track,
            "musicEmotion": predicted_emotion,
            "musicEmotionScore": round(float(confidence), 4),
        }
        scored.append((base_score, enriched))

    # Sort by score DESC, with stable random tie-breaking
    random.shuffle(scored)
    scored.sort(key=lambda item: item[0], reverse=True)

    selected: List[Dict[str, str]] = []
    artist_caps: Dict[str, int] = defaultdict(int)
    artist_overflow: List[Dict[str, str]] = []

    for _score, track in scored:
        artist_key = (track.get("artist") or "").strip().lower()
        if _is_near_duplicate(track, selected):
            continue
        if artist_key and artist_caps[artist_key] >= 2:
            artist_overflow.append(track)
            continue
        selected.append(track)
        if artist_key:
            artist_caps[artist_key] += 1
        if len(selected) >= 30:
            return selected

    for track in artist_overflow:
        if _is_near_duplicate(track, selected):
            continue
        selected.append(track)
        if len(selected) >= 30:
            break

    return selected


def _audio_similarity(features: Dict[str, float], targets: Dict[str, float]) -> float:
    """Similarity in [0, 1] between actual track features and target audio profile.

    Each dimension contributes proportional to how close the track is to the
    target.  Tempo is normalised by its expected range (40–200 BPM).
    """
    if not features:
        return 0.5

    differences: List[float] = []
    if "valence" in targets:
        differences.append(abs(features.get("valence", 0.5) - targets["valence"]))
    if "energy" in targets:
        differences.append(abs(features.get("energy", 0.5) - targets["energy"]))
    if "danceability" in targets:
        differences.append(abs(features.get("danceability", 0.5) - targets["danceability"]))
    if "acousticness" in targets:
        differences.append(abs(features.get("acousticness", 0.4) - targets["acousticness"]))
    if "tempo" in targets:
        diff_bpm = abs(features.get("tempo", 100.0) - targets["tempo"])
        differences.append(min(diff_bpm / 80.0, 1.0))

    if not differences:
        return 0.5

    mean_diff = sum(differences) / len(differences)
    return max(0.0, min(1.0, 1.0 - mean_diff))


def _emotion_from_features(features: Dict[str, float]) -> Emotion:
    """Find which preset emotion profile this track is closest to."""
    best_emotion: Emotion = "neutral"
    best_similarity = -1.0
    for emotion in EMOTIONS:
        sim = _audio_similarity(features, EMOTION_AUDIO_TARGETS[emotion])
        if sim > best_similarity:
            best_similarity = sim
            best_emotion = emotion
    return best_emotion


def _randomise_audio_targets(targets: Dict[str, float]) -> Dict[str, float]:
    """Add small jitter to target audio values so consecutive requests vary.

    Magnitudes are small enough that mood stays the same: ±0.06 for the
    0-1 features and ±8 BPM for tempo.
    """
    randomised: Dict[str, float] = {}
    for key, value in targets.items():
        if key == "tempo":
            randomised[key] = max(40.0, min(200.0, value + random.uniform(-8.0, 8.0)))
        else:
            randomised[key] = max(0.05, min(0.95, value + random.uniform(-0.06, 0.06)))
    return randomised


def _quality_bonus(track: Dict[str, str]) -> float:
    bonus = 0.0
    if track.get("previewUrl"):
        bonus += 0.30
    if track.get("coverUrl"):
        bonus += 0.10
    if track.get("source") == "spotify":
        bonus += 0.08
    elif track.get("source") == "itunes":
        bonus += 0.04

    duration_seconds = _parse_duration_seconds(track.get("duration", ""))
    if 110 <= duration_seconds <= 360:
        bonus += 0.05
    elif duration_seconds == 0:
        bonus -= 0.05

    return bonus


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
    keys = ("valence", "energy", "tempo", "danceability", "acousticness")
    values: Dict[str, float] = {key: 0.0 for key in keys}

    for emotion, weight in weights.items():
        targets = EMOTION_AUDIO_TARGETS[emotion]
        for key in keys:
            values[key] += weight * targets.get(key, 0.0)

    return {
        "valence": round(_clamp_unit(values["valence"]), 3),
        "energy": round(_clamp_unit(values["energy"]), 3),
        "tempo": round(_clamp_tempo(values["tempo"] or 100.0), 1),
        "danceability": round(_clamp_unit(values["danceability"] or 0.5), 3),
        "acousticness": round(_clamp_unit(values["acousticness"] or 0.4), 3),
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
    """Randomised mood + genre queries.

    Each call samples a different subset of mood terms so that consecutive
    requests for the same emotion still produce a noticeably different
    set of tracks.
    """
    dominant_emotions = [
        emotion
        for emotion, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True)
        if weight > 0
    ]
    if not dominant_emotions:
        dominant_emotions = ["neutral"]

    queries: List[str] = []

    for emotion in dominant_emotions[:2]:
        all_terms = EMOTION_MOOD_TERMS[emotion]
        sample_size = min(4, len(all_terms))
        terms = random.sample(all_terms, sample_size)
        for genre in seed_genres:
            for term in terms[:2]:
                queries.append(f"{genre} {term}")
                queries.append(f"{term} {genre}")
        queries.extend(terms[:3])

    queries.extend(seed_genres)
    random.shuffle(queries)

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
    """Plain-language randomised queries for iTunes Search."""

    queries: List[str] = []
    all_terms = EMOTION_MOOD_TERMS[dominant_emotion]
    dominant_terms = random.sample(all_terms, min(4, len(all_terms)))

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
        extra_terms = random.sample(
            EMOTION_MOOD_TERMS[emotion],
            min(2, len(EMOTION_MOOD_TERMS[emotion])),
        )
        queries.extend(extra_terms)

    random.shuffle(queries)
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
