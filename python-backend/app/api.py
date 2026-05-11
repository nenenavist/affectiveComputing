from fastapi import APIRouter, Depends, Header, HTTPException

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
    SpotifyAuthUrl,
    SpotifyCreatePlaylistRequest,
    SpotifyCreatePlaylistResponse,
    SpotifyStatus,
    SpotifyTokenRequest,
    SpotifyTokenResponse,
    User,
)
from app.spotify_service import build_authorize_url, create_user_playlist, exchange_code, is_spotify_configured


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


@router.get("/spotify/auth-url", response_model=SpotifyAuthUrl)
async def spotify_auth_url(redirect_uri: str, state: str = "music-mood"):
    url = build_authorize_url(redirect_uri=redirect_uri, state=state)
    if not url:
        raise HTTPException(status_code=503, detail="Spotify credentials are not configured.")

    return SpotifyAuthUrl(url=url)


@router.post("/spotify/token", response_model=SpotifyTokenResponse)
async def spotify_token(request: SpotifyTokenRequest):
    token = exchange_code(code=request.code, redirect_uri=request.redirectUri)
    if not token:
        raise HTTPException(status_code=503, detail="Не удалось получить Spotify token.")

    return SpotifyTokenResponse(
        accessToken=str(token["access_token"]),
        tokenType=str(token.get("token_type", "Bearer")),
        expiresIn=int(token.get("expires_in", 3600)),
    )


@router.post("/spotify/playlists", response_model=SpotifyCreatePlaylistResponse)
async def spotify_create_playlist(request: SpotifyCreatePlaylistRequest):
    playlist = create_user_playlist(
        access_token=request.accessToken,
        name=request.name,
        tracks=[track.model_dump() for track in request.tracks],
    )
    if not playlist:
        raise HTTPException(status_code=503, detail="Не удалось создать Spotify playlist.")

    return SpotifyCreatePlaylistResponse(id=playlist["id"], url=playlist["url"])


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

    return build_playlist(request)


@router.post("/music/emotion", response_model=MusicEmotionResponse)
async def detect_music_emotion(request: MusicEmotionRequest):
    return analyze_music_emotion(
        title=request.title,
        artist=request.artist,
        tags=request.tags,
    )
