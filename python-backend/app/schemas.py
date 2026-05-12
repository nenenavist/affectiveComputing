from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Emotion = Literal["happy", "sad", "angry", "neutral"]
EmotionWeights = Dict[Emotion, float]


class MoodRequest(BaseModel):
    text: str = ""
    hasCameraCapture: bool = False
    image: Optional[str] = Field(default=None, description="Optional base64 camera snapshot.")


class Track(BaseModel):
    id: str
    title: str
    artist: str
    duration: str
    coverUrl: str
    spotifyUrl: str
    previewUrl: Optional[str] = None
    source: Optional[str] = None
    musicEmotion: Optional[Emotion] = None
    musicEmotionScore: Optional[float] = None
    musicTags: List[str] = Field(default_factory=list)


class Playlist(BaseModel):
    id: str
    playlistId: Optional[str] = None
    name: str
    emotion: Emotion
    emotionWeights: EmotionWeights = Field(
        default_factory=lambda: {"happy": 0.0, "sad": 0.0, "angry": 0.0, "neutral": 1.0}
    )
    spotifyUrl: str
    tracks: List[Track]
    audioTargets: Dict[str, float] = Field(default_factory=dict)
    seedGenres: List[str] = Field(default_factory=list)


class SavedPlaylist(Playlist):
    timestamp: str


class MusicEmotionRequest(BaseModel):
    title: str
    artist: str
    tags: List[str] = Field(default_factory=list)


class MusicEmotionResponse(BaseModel):
    emotion: Emotion
    score: float
    tags: List[str]
    source: str


class User(BaseModel):
    id: int
    email: str


class AuthRequest(BaseModel):
    email: str
    password: str


class ProfileSnapshot(BaseModel):
    savedPlaylists: List[SavedPlaylist] = Field(default_factory=list)
    likedTracks: List[Track] = Field(default_factory=list)


class AuthResponse(BaseModel):
    token: str
    user: User
    profile: ProfileSnapshot


class SpotifyStatus(BaseModel):
    configured: bool


class YoutubeSearchResponse(BaseModel):
    videoId: Optional[str] = None
