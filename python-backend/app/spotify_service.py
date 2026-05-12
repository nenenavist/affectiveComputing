import base64
import json
import logging
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
MARKET = "US"
TOKEN_REQUEST_TIMEOUT = 20
SEARCH_REQUEST_TIMEOUT = 18
TOKEN_RETRY_ATTEMPTS = 3
SEARCH_RETRY_ATTEMPTS = 3
NETWORK_TIMEOUT_STATUS = 504
_TOKEN_CACHE: Dict[str, object] = {"access_token": None, "expires_at": 0.0}
# Set to False after the first 404/403 from /recommendations so we don't
# keep wasting requests on a deprecated endpoint.
_RECOMMENDATIONS_AVAILABLE = True
_logger = logging.getLogger(__name__)


class SpotifyApiError(RuntimeError):
    """Raised when Spotify Web API responds with a meaningful error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Spotify API {status_code}: {message}")
        self.status_code = status_code
        self.message = message


def _credentials() -> tuple[Optional[str], Optional[str]]:
    return os.getenv("SPOTIFY_CLIENT_ID"), os.getenv("SPOTIFY_CLIENT_SECRET")


def is_spotify_configured() -> bool:
    client_id, client_secret = _credentials()
    return bool(client_id and client_secret)


def _is_network_timeout(error: BaseException) -> bool:
    """Detect transient network timeouts that justify a retry/fallback."""
    if isinstance(error, (socket.timeout, TimeoutError)):
        return True
    if isinstance(error, URLError) and isinstance(error.reason, (socket.timeout, TimeoutError)):
        return True
    return False


def get_app_access_token() -> Optional[str]:
    cached_token = _TOKEN_CACHE.get("access_token")
    expires_at = float(_TOKEN_CACHE.get("expires_at") or 0)
    if cached_token and time.time() < expires_at:
        return str(cached_token)

    client_id, client_secret = _credentials()
    if not client_id or not client_secret:
        return None

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    request = Request(
        SPOTIFY_TOKEN_URL,
        data=urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    payload: Optional[Dict[str, object]] = None
    last_error: Optional[BaseException] = None

    for attempt in range(TOKEN_RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=TOKEN_REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            _logger.warning("Spotify token rejected (HTTP %s): %s", error.code, error.reason)
            raise SpotifyApiError(error.code, str(error.reason)) from error
        except Exception as error:
            last_error = error
            _logger.warning(
                "Spotify token request failed (attempt %s/%s): %s",
                attempt + 1,
                TOKEN_RETRY_ATTEMPTS,
                error,
            )
            if attempt < TOKEN_RETRY_ATTEMPTS - 1:
                time.sleep(0.6 * (attempt + 1))

    if payload is None:
        if last_error is not None and _is_network_timeout(last_error):
            raise SpotifyApiError(
                NETWORK_TIMEOUT_STATUS,
                "Сервер Spotify не отвечает (таймаут сети при получении токена).",
            )
        raise SpotifyApiError(
            NETWORK_TIMEOUT_STATUS,
            f"Не удалось получить токен Spotify: {last_error}",
        )

    access_token = payload.get("access_token")
    if not access_token:
        raise SpotifyApiError(401, "Spotify не вернул access_token. Проверьте SPOTIFY_CLIENT_ID/SECRET.")

    _TOKEN_CACHE["access_token"] = access_token
    _TOKEN_CACHE["expires_at"] = time.time() + int(payload.get("expires_in", 3600)) - 60
    return str(access_token)


def search_tracks_for_mood(queries: List[str], limit: int = 30) -> List[Dict[str, str]]:
    """Build recommendations on top of Spotify /search (parallel queries)."""

    raw_items: List[Dict[str, object]] = []
    last_error: Optional[SpotifyApiError] = None

    # Run all queries concurrently — typical wall-clock time drops from
    # O(n * latency) to O(1 * latency).
    with ThreadPoolExecutor(max_workers=min(len(queries), 6)) as pool:
        future_to_query = {pool.submit(_search_query, q): q for q in queries}
        for future in as_completed(future_to_query):
            try:
                items = future.result()
                raw_items.extend(items)
            except SpotifyApiError as error:
                last_error = error

    if not raw_items and last_error is not None:
        raise last_error

    with_preview = _format_unique_tracks(raw_items, require_preview=True)
    if len(with_preview) >= limit:
        return with_preview[:limit]

    fallback_pool = _format_unique_tracks(raw_items, require_preview=False)
    combined: List[Dict[str, str]] = []
    seen: set[str] = set()

    for track in with_preview + fallback_pool:
        if track["id"] in seen:
            continue
        seen.add(track["id"])
        combined.append(track)
        if len(combined) >= limit:
            break

    return combined


def get_recommendations(
    seed_genres: List[str],
    audio_targets: Dict[str, float],
    limit: int = 30,
    market: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Spotify /v1/recommendations — selects tracks by AUDIO features, not titles.

    Accepts:
        seed_genres   — up to 5 seed genres (e.g. ["pop", "dance", "indie"]).
        audio_targets — any of: valence, energy, tempo, danceability,
                        acousticness, instrumentalness, speechiness, etc.
        limit         — number of tracks to fetch (max 100).

    Returns a list of formatted tracks.  Raises SpotifyApiError on failure.
    """
    global _RECOMMENDATIONS_AVAILABLE
    if not _RECOMMENDATIONS_AVAILABLE:
        raise SpotifyApiError(404, "Spotify /recommendations is deprecated for this app.")

    token = get_app_access_token()
    if not token:
        raise SpotifyApiError(401, "Spotify access token is unavailable.")

    safe_seed_genres = [g.strip().lower() for g in seed_genres if g and g.strip()][:5]
    if not safe_seed_genres:
        safe_seed_genres = ["pop"]

    params: Dict[str, str] = {
        "seed_genres": ",".join(safe_seed_genres),
        "limit": str(max(1, min(int(limit), 100))),
        "market": market or MARKET,
    }
    for key, value in audio_targets.items():
        if value is None:
            continue
        params[f"target_{key}"] = f"{float(value):.3f}"

    request = Request(
        f"{SPOTIFY_API_URL}/recommendations?{urlencode(params)}",
        headers={"Authorization": f"Bearer {token}"},
    )

    last_exception: Optional[BaseException] = None
    for attempt in range(SEARCH_RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=SEARCH_REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            items = payload.get("tracks", []) or []
            formatted = _format_unique_tracks(items, require_preview=True)
            if len(formatted) < limit // 2:
                formatted += [
                    t for t in _format_unique_tracks(items, require_preview=False)
                    if t["id"] not in {x["id"] for x in formatted}
                ]
            return formatted[:limit]
        except HTTPError as error:
            if error.code in (403, 404):
                # Endpoint is deprecated for this app — don't try again this session.
                _RECOMMENDATIONS_AVAILABLE = False
                _logger.info(
                    "Disabling Spotify /recommendations for this session (HTTP %s).",
                    error.code,
                )
            message = _extract_api_message(error)
            raise SpotifyApiError(error.code, message) from error
        except Exception as error:
            last_exception = error
            _logger.warning(
                "Spotify recommendations failed (attempt %s/%s): %s",
                attempt + 1, SEARCH_RETRY_ATTEMPTS, error,
            )
            if attempt < SEARCH_RETRY_ATTEMPTS - 1:
                time.sleep(0.5 * (attempt + 1))

    if last_exception is not None and _is_network_timeout(last_exception):
        raise SpotifyApiError(
            NETWORK_TIMEOUT_STATUS, f"Таймаут recommendations: {last_exception}"
        )
    raise SpotifyApiError(503, f"Spotify recommendations failed: {last_exception}")


_AUDIO_FEATURES_AVAILABLE = True


def get_audio_features(track_ids: List[str]) -> Dict[str, Dict[str, float]]:
    """Fetch audio features for up to 100 tracks per call.  Returns {id: features}."""
    global _AUDIO_FEATURES_AVAILABLE
    if not track_ids or not _AUDIO_FEATURES_AVAILABLE:
        return {}

    token = get_app_access_token()
    if not token:
        return {}

    results: Dict[str, Dict[str, float]] = {}
    for batch_start in range(0, len(track_ids), 100):
        batch = track_ids[batch_start:batch_start + 100]
        params = {"ids": ",".join(batch)}
        request = Request(
            f"{SPOTIFY_API_URL}/audio-features?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urlopen(request, timeout=SEARCH_REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for feature in payload.get("audio_features", []) or []:
                if not isinstance(feature, dict) or not feature.get("id"):
                    continue
                results[str(feature["id"])] = {
                    "valence": float(feature.get("valence") or 0.0),
                    "energy": float(feature.get("energy") or 0.0),
                    "tempo": float(feature.get("tempo") or 0.0),
                    "danceability": float(feature.get("danceability") or 0.0),
                    "acousticness": float(feature.get("acousticness") or 0.0),
                    "instrumentalness": float(feature.get("instrumentalness") or 0.0),
                }
        except HTTPError as error:
            if error.code in (403, 404):
                _AUDIO_FEATURES_AVAILABLE = False
                _logger.info(
                    "Disabling Spotify /audio-features for this session (HTTP %s).",
                    error.code,
                )
                return results
            _logger.warning("Audio-features batch failed: %s", error)
            continue
        except Exception as error:
            _logger.warning("Audio-features batch failed: %s", error)
            continue

    return results


def search_track_metadata(title: str, artist: str) -> Optional[Dict[str, str]]:
    """Look up a single track by title/artist, used as metadata enrichment helper."""

    queries = (
        f'track:"{title}" artist:"{artist}"',
        f"{artist} {title}",
    )

    for query in queries:
        try:
            items = _search_query(query, limit=1, offset=0)
        except SpotifyApiError:
            continue

        for item in items:
            formatted = _format_track(item)
            if formatted:
                return formatted

    return None


def _search_query(query: str, limit: int = 20, offset: Optional[int] = None) -> List[Dict[str, object]]:
    """Call Spotify /search; raise SpotifyApiError when API is unavailable."""

    token = get_app_access_token()
    if not token:
        raise SpotifyApiError(401, "Spotify access token is unavailable.")

    # Spotify recently tightened /search to limit ≤ 20 for new applications.
    safe_limit = max(1, min(int(limit), 20))
    safe_offset = max(0, min(int(offset or 0), 950))
    params = {
        "q": query,
        "type": "track",
        "market": MARKET,
        "limit": str(safe_limit),
        "offset": str(safe_offset),
    }

    request = Request(
        f"{SPOTIFY_API_URL}/search?{urlencode(params)}",
        headers={"Authorization": f"Bearer {token}"},
    )

    last_exception: Optional[BaseException] = None
    for attempt in range(SEARCH_RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=SEARCH_REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("tracks", {}).get("items", []) or []
        except HTTPError as error:
            message = _extract_api_message(error)
            raise SpotifyApiError(error.code, message) from error
        except Exception as error:
            last_exception = error
            _logger.warning(
                "Spotify search failed (attempt %s/%s) for %r: %s",
                attempt + 1,
                SEARCH_RETRY_ATTEMPTS,
                query,
                error,
            )
            if attempt < SEARCH_RETRY_ATTEMPTS - 1:
                time.sleep(0.5 * (attempt + 1))

    if last_exception is not None and _is_network_timeout(last_exception):
        raise SpotifyApiError(NETWORK_TIMEOUT_STATUS, f"Таймаут поиска Spotify: {last_exception}")
    raise SpotifyApiError(503, f"Spotify request failed: {last_exception}")


def _extract_api_message(error: HTTPError) -> str:
    try:
        body = json.loads(error.read().decode("utf-8"))
        return str(body.get("error", {}).get("message") or error.reason)
    except Exception:
        return str(error.reason)


def _format_track(track: Dict[str, object], require_preview: bool = True) -> Optional[Dict[str, str]]:
    track_id = str(track.get("id") or "")
    preview_url = track.get("preview_url")
    available_markets = track.get("available_markets") or []
    is_playable = track.get("is_playable", True)

    if not track_id or not is_playable:
        return None

    if available_markets and MARKET not in available_markets:
        return None

    if require_preview and not preview_url:
        return None

    album = track.get("album") if isinstance(track.get("album"), dict) else {}
    images = album.get("images", []) if isinstance(album, dict) else []
    artists = track.get("artists", [])

    return {
        "id": track_id,
        "title": str(track.get("name") or "Untitled track"),
        "artist": ", ".join(
            str(artist.get("name")) for artist in artists if isinstance(artist, dict)
        ),
        "spotifyUrl": f"https://open.spotify.com/track/{track_id}",
        "previewUrl": str(preview_url) if preview_url else None,
        "coverUrl": images[0]["url"] if images and isinstance(images[0], dict) else "",
        "duration": _format_duration(int(track.get("duration_ms") or 0)),
        "source": "spotify",
    }


def _format_duration(duration_ms: int) -> str:
    total_seconds = max(0, duration_ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _format_unique_tracks(
    tracks: List[Dict[str, object]],
    require_preview: bool,
) -> List[Dict[str, str]]:
    formatted_tracks: List[Dict[str, str]] = []
    seen: set[str] = set()

    for track in tracks:
        formatted = _format_track(track, require_preview=require_preview)
        if not formatted:
            continue

        if formatted["id"] in seen:
            continue

        seen.add(formatted["id"])
        formatted_tracks.append(formatted)

    return formatted_tracks
