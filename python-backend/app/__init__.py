import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router as api_router
from app.db import init_db


def _cors_origins() -> list[str]:
    """Comma-separated URLs in ALLOWED_ORIGINS (e.g. https://app.vercel.app)."""
    defaults = ["http://localhost:5173", "http://127.0.0.1:5173"]
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return defaults
    extra = [o.strip() for o in raw.split(",") if o.strip()]
    return list(dict.fromkeys(defaults + extra))


def create_app() -> FastAPI:
    init_db()

    static_dir = os.getenv("STATIC_DIR", "").strip()
    static_path = Path(static_dir) if static_dir else None
    serve_spa = static_path is not None and static_path.is_dir()

    app = FastAPI(
        title="Music Mood Matcher API",
        docs_url="/api/docs" if serve_spa else "/docs",
        redoc_url="/api/redoc" if serve_spa else "/redoc",
        openapi_url="/api/openapi.json" if serve_spa else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    if serve_spa:
        assets_dir = static_path / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="vite_assets")

        index_file = static_path / "index.html"

        @app.get("/")
        async def spa_root() -> FileResponse:
            if not index_file.is_file():
                raise HTTPException(status_code=404, detail="index.html missing")
            return FileResponse(index_file)

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            if not index_file.is_file():
                raise HTTPException(status_code=404, detail="index.html missing")
            return FileResponse(index_file)
    else:

        @app.get("/")
        async def read_root() -> dict[str, str]:
            return {"message": "Music Mood Matcher API is running"}

    return app
