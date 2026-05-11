from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Emotion = Literal["happy", "sad", "angry", "neutral"]


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
    musicEmotion: Optional[Emotion] = None
    musicEmotionScore: Optional[float] = None
    musicTags: List[str] = Field(default_factory=list)


class Playlist(BaseModel):
    id: str
    name: str
    emotion: Emotion
    spotifyUrl: str
    tracks: List[Track]


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


class SpotifyAuthUrl(BaseModel):
    url: str


class SpotifyTokenRequest(BaseModel):
    code: str
    redirectUri: str


class SpotifyTokenResponse(BaseModel):
    accessToken: str
    tokenType: str
    expiresIn: int


class SpotifyCreatePlaylistRequest(BaseModel):
    accessToken: str
    name: str
    tracks: List[Track]


class SpotifyCreatePlaylistResponse(BaseModel):
    id: str
    url: str
