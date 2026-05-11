from fastapi import APIRouter, HTTPException

from app.models import MoodRequest, Playlist
from app.utils import build_playlist

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
