import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


DB_PATH = Path(__file__).resolve().parents[1] / "music_mood.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                saved_playlists TEXT NOT NULL DEFAULT '[]',
                liked_tracks TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
    with get_connection() as connection:
        return connection.execute(query, params).fetchone()


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with get_connection() as connection:
        connection.execute(query, params)


def read_profile(user_id: int) -> Dict[str, Any]:
    row = fetch_one("SELECT saved_playlists, liked_tracks FROM user_profiles WHERE user_id = ?", (user_id,))
    if not row:
        execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))
        return {"savedPlaylists": [], "likedTracks": []}

    return {
        "savedPlaylists": json.loads(row["saved_playlists"]),
        "likedTracks": json.loads(row["liked_tracks"]),
    }


def write_profile(user_id: int, saved_playlists: list[dict[str, Any]], liked_tracks: list[dict[str, Any]]) -> None:
    execute(
        """
        INSERT INTO user_profiles (user_id, saved_playlists, liked_tracks, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            saved_playlists = excluded.saved_playlists,
            liked_tracks = excluded.liked_tracks,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, json.dumps(saved_playlists), json.dumps(liked_tracks)),
    )
