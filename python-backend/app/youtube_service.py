import json
import os
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search_youtube_video(query: str) -> Optional[str]:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key or not query.strip():
        return None

    params = urlencode(
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": "1",
            "videoEmbeddable": "true",
            "key": api_key,
        }
    )
    request = Request(f"{YOUTUBE_SEARCH_URL}?{params}")

    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if video_id:
            return video_id

    return None
