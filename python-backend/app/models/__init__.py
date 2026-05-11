from typing import Literal, Optional

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


class Playlist(BaseModel):
    id: str
    name: str
    emotion: Emotion
    spotifyUrl: str
    tracks: list[Track]
