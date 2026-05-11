from typing import Dict, List

from app.ml import detect_emotion
from app.music import analyze_music_emotion
from app.schemas import Emotion, MoodRequest, Playlist, Track
from app.spotify_service import search_tracks


COVERS = [
    "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=320&q=80",
    "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=320&q=80",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=320&q=80",
    "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=320&q=80",
    "https://images.unsplash.com/photo-1494232410401-ad00d5433cfa?auto=format&fit=crop&w=320&q=80",
    "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=320&q=80",
]


TRACKS_BY_EMOTION: Dict[Emotion, List[Dict[str, str]]] = {
    "happy": [
        {"id": "happy-1", "title": "Happy", "artist": "Pharrell Williams", "duration": "3:53"},
        {"id": "happy-2", "title": "Walking on Sunshine", "artist": "Katrina and the Waves", "duration": "3:58"},
        {"id": "happy-3", "title": "Can't Stop the Feeling!", "artist": "Justin Timberlake", "duration": "3:56"},
        {"id": "happy-4", "title": "Good as Hell", "artist": "Lizzo", "duration": "2:39"},
        {"id": "happy-5", "title": "September", "artist": "Earth, Wind & Fire", "duration": "3:35"},
    ],
    "sad": [
        {"id": "sad-1", "title": "Someone Like You", "artist": "Adele", "duration": "4:45"},
        {"id": "sad-2", "title": "The Night We Met", "artist": "Lord Huron", "duration": "3:28"},
        {"id": "sad-3", "title": "Skinny Love", "artist": "Bon Iver", "duration": "3:58"},
        {"id": "sad-4", "title": "Fix You", "artist": "Coldplay", "duration": "4:55"},
        {"id": "sad-5", "title": "Hurt", "artist": "Johnny Cash", "duration": "3:38"},
    ],
    "angry": [
        {"id": "angry-1", "title": "Break Stuff", "artist": "Limp Bizkit", "duration": "2:46"},
        {"id": "angry-2", "title": "Killing in the Name", "artist": "Rage Against The Machine", "duration": "5:14"},
        {"id": "angry-3", "title": "Bodies", "artist": "Drowning Pool", "duration": "3:22"},
        {"id": "angry-4", "title": "Duality", "artist": "Slipknot", "duration": "4:12"},
        {"id": "angry-5", "title": "Given Up", "artist": "Linkin Park", "duration": "3:09"},
    ],
    "neutral": [
        {"id": "neutral-1", "title": "Weightless", "artist": "Marconi Union", "duration": "8:08"},
        {"id": "neutral-2", "title": "Avril 14th", "artist": "Aphex Twin", "duration": "2:05"},
        {"id": "neutral-3", "title": "Gymnopédie No. 1", "artist": "Erik Satie", "duration": "3:05"},
        {"id": "neutral-4", "title": "An Ending (Ascent)", "artist": "Brian Eno", "duration": "4:24"},
        {"id": "neutral-5", "title": "Blue in Green", "artist": "Miles Davis", "duration": "5:37"},
    ],
}


PLAYLIST_NAMES: Dict[Emotion, str] = {
    "happy": "Пастельный утренний заряд",
    "sad": "Мягкий дождливый вечер",
    "angry": "Выпустить напряжение",
    "neutral": "Ровный дневной ритм",
}


MUSIC_TAGS_BY_EMOTION: Dict[Emotion, List[str]] = {
    "happy": ["happy", "pop", "dance", "summer", "fun"],
    "sad": ["sad", "melancholic", "rain", "acoustic", "chill"],
    "angry": ["angry", "rage", "metal", "hard rock", "punk"],
    "neutral": ["neutral", "ambient", "calm", "instrumental", "jazz"],
}


def build_playlist(request: MoodRequest) -> Playlist:
    emotion = detect_emotion(request)
    playlist_id = f"mmm-{emotion}-playlist"
    tracks = []

    resolved_tracks = search_tracks(TRACKS_BY_EMOTION[emotion])

    for index, track in enumerate(resolved_tracks):
        cover_url = track.get("coverUrl") or COVERS[index % len(COVERS)]
        spotify_url = track.get("spotifyUrl") or _spotify_search_url(track["title"], track["artist"])
        music_emotion = analyze_music_emotion(
            title=track["title"],
            artist=track["artist"],
            tags=MUSIC_TAGS_BY_EMOTION[emotion],
        )
        tracks.append(
            Track(
                id=track["id"],
                title=track["title"],
                artist=track["artist"],
                duration=track["duration"],
                coverUrl=cover_url,
                spotifyUrl=spotify_url,
                musicEmotion=music_emotion.emotion,
                musicEmotionScore=music_emotion.score,
                musicTags=music_emotion.tags,
            )
        )

    return Playlist(
        id=playlist_id,
        name=PLAYLIST_NAMES[emotion],
        emotion=emotion,
        spotifyUrl=f"https://open.spotify.com/playlist/{playlist_id}",
        tracks=tracks,
    )


def _spotify_search_url(title: str, artist: str) -> str:
    query = f"{artist} {title}".replace(" ", "%20")
    return f"https://open.spotify.com/search/{query}"
