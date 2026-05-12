"""iTunes Search API fallback (no API key required).

Used when Spotify is unavailable. Returns tracks in the same shape that
``spotify_service`` produces so the rest of the pipeline does not change.
"""

import json
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
REQUEST_TIMEOUT = 8
RETRY_ATTEMPTS = 2
_logger = logging.getLogger(__name__)


def _is_network_timeout(error: BaseException) -> bool:
    if isinstance(error, (socket.timeout, TimeoutError)):
        return True
    if isinstance(error, URLError) and isinstance(error.reason, (socket.timeout, TimeoutError)):
        return True
    return False


def search_tracks_for_mood(queries: List[str], limit: int = 30) -> List[Dict[str, str]]:
    """Build a mood-based track list from iTunes Search (parallel queries)."""

    raw_batches: List[List[Dict[str, object]]] = []

    with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as pool:
        futures = {pool.submit(_search_query, q, 25): q for q in queries}
        for future in as_completed(futures):
            try:
                raw_batches.append(future.result())
            except Exception:
                pass

    collected: List[Dict[str, str]] = []
    seen: set[str] = set()

    for batch in raw_batches:
        for item in batch:
            track = _format_track(item)
            if not track or track["id"] in seen:
                continue
            seen.add(track["id"])
            collected.append(track)

    return collected[:limit]


def _search_query(query: str, limit: int = 25) -> List[Dict[str, object]]:
    params = {
        "term": query,
        "entity": "song",
        "media": "music",
        "limit": str(limit),
    }
    request = Request(
        f"{ITUNES_SEARCH_URL}?{urlencode(params)}",
        headers={
            "User-Agent": "mood-music-machine/1.0 (+https://localhost)",
            "Accept": "application/json",
        },
    )

    last_error: Optional[BaseException] = None

    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("results", []) or []
        except HTTPError as error:
            _logger.warning("iTunes search HTTP error (%s) for %r", error.code, query)
            return []
        except Exception as error:
            last_error = error
            _logger.warning(
                "iTunes search failed (attempt %s/%s) for %r: %s",
                attempt + 1,
                RETRY_ATTEMPTS,
                query,
                error,
            )
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(0.4 * (attempt + 1))

    if last_error is not None and not _is_network_timeout(last_error):
        _logger.warning("iTunes search exhausted retries for %r: %s", query, last_error)
    return []


def _format_track(item: Dict[str, object]) -> Optional[Dict[str, str]]:
    track_id_raw = item.get("trackId")
    title = item.get("trackName")
    artist = item.get("artistName")
    preview_url = item.get("previewUrl")

    if not track_id_raw or not title or not artist:
        return None

    artwork = item.get("artworkUrl100") or item.get("artworkUrl60") or ""
    if isinstance(artwork, str) and artwork:
        artwork = artwork.replace("100x100bb.jpg", "600x600bb.jpg")

    duration_ms = int(item.get("trackTimeMillis") or 0)
    track_view_url = item.get("trackViewUrl") or ""

    return {
        "id": f"itunes-{track_id_raw}",
        "title": str(title),
        "artist": str(artist),
        "duration": _format_duration(duration_ms),
        "coverUrl": str(artwork) if artwork else "",
        "spotifyUrl": str(track_view_url),
        "previewUrl": str(preview_url) if preview_url else None,
        "source": "itunes",
    }


def _format_duration(duration_ms: int) -> str:
    total_seconds = max(0, duration_ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"
