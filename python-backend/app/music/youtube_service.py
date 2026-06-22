import json
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.io",
    "https://piped-api.garudalinux.org",
]


def search_youtube_video(title: str, artist: str) -> Optional[str]:
    """Search YouTube for a video and return the video ID using Piped API."""
    query = f"{artist} {title}"
    
    for instance in PIPED_INSTANCES:
        try:
            params = urlencode({"q": query, "filter": "music_songs"})
            request = Request(
                f"{instance}/search?{params}",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                items = data.get("items", [])
                
                if items and len(items) > 0:
                    # Get the first video result
                    video_id = items[0].get("url", "").split("/watch?v=")[-1]
                    if video_id:
                        return video_id
        except Exception as e:
            print(f"Error searching with {instance}: {e}")
            continue
    
    return None
