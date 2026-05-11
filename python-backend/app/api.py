from fastapi import APIRouter, HTTPException

from app.playlist_service import build_playlist
from app.schemas import MoodRequest, Playlist


router = APIRouter(prefix="/api")


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/mood/playlist", response_model=Playlist)
async def generate_mood_playlist(request: MoodRequest):
    if "api error" in request.text.lower():
        raise HTTPException(
            status_code=503,
            detail="Анализ настроения временно недоступен. Попробуйте ещё раз.",
        )

    return build_playlist(request)
