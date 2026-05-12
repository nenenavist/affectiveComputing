from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.auth_service import get_profile, get_user_by_token, login_user, register_user, sync_profile
from app.music import analyze_music_emotion
from app.playlist_service import build_playlist
from app.schemas import (
    AuthRequest,
    AuthResponse,
    MoodRequest,
    MusicEmotionRequest,
    MusicEmotionResponse,
    Playlist,
    ProfileSnapshot,
    SpotifyStatus,
    User,
    YoutubeSearchResponse,
)
from app.spotify_service import is_spotify_configured
from app.youtube_service import search_youtube_video


router = APIRouter(prefix="/api")


def current_user(authorization: str = Header(default="")) -> User:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Нужна авторизация.")

    try:
        return get_user_by_token(token)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/spotify/status", response_model=SpotifyStatus)
async def spotify_status():
    return SpotifyStatus(configured=is_spotify_configured())


@router.post("/auth/register", response_model=AuthResponse)
async def register(request: AuthRequest):
    try:
        return register_user(request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: AuthRequest):
    try:
        return login_user(request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@router.get("/profile", response_model=ProfileSnapshot)
async def read_profile(user: User = Depends(current_user)):
    return get_profile(user.id)


@router.put("/profile", response_model=ProfileSnapshot)
async def update_profile(profile: ProfileSnapshot, user: User = Depends(current_user)):
    return sync_profile(user.id, profile)


@router.post("/mood/playlist", response_model=Playlist)
async def generate_mood_playlist(request: MoodRequest):
    if "api error" in request.text.lower():
        raise HTTPException(
            status_code=503,
            detail="Анализ настроения временно недоступен. Попробуйте ещё раз.",
        )

    try:
        return build_playlist(request)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/youtube/search", response_model=YoutubeSearchResponse)
async def youtube_search(q: str = Query(min_length=1)):
    return YoutubeSearchResponse(videoId=search_youtube_video(q))


@router.post("/music/emotion", response_model=MusicEmotionResponse)
async def detect_music_emotion(request: MusicEmotionRequest):
    return analyze_music_emotion(
        title=request.title,
        artist=request.artist,
        tags=request.tags,
    )
