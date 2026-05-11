from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.db import init_db


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(title="Music Mood Matcher API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def read_root():
        return {"message": "Music Mood Matcher API is running"}

    app.include_router(api_router)
    return app
