import hashlib
import hmac
import secrets
from typing import Optional

from app.db import execute, fetch_one, read_profile, write_profile
from app.schemas import AuthResponse, ProfileSnapshot, User


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    resolved_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), resolved_salt.encode("utf-8"), 120_000)
    return f"{resolved_salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    salt, _ = stored_hash.split("$", 1)
    return hmac.compare_digest(_hash_password(password, salt), stored_hash)


def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def _to_user(row) -> User:  # type: ignore[no-untyped-def]
    return User(id=row["id"], email=row["email"])


def register_user(email: str, password: str) -> AuthResponse:
    normalized_email = email.strip().lower()
    if len(password) < 6:
        raise ValueError("Пароль должен быть не короче 6 символов.")

    try:
        execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (normalized_email, _hash_password(password)),
        )
    except Exception as error:
        raise ValueError("Пользователь с таким email уже существует.") from error

    row = fetch_one("SELECT id, email FROM users WHERE email = ?", (normalized_email,))
    token = _create_session(int(row["id"]))
    return AuthResponse(token=token, user=_to_user(row), profile=ProfileSnapshot())


def login_user(email: str, password: str) -> AuthResponse:
    normalized_email = email.strip().lower()
    row = fetch_one("SELECT id, email, password_hash FROM users WHERE email = ?", (normalized_email,))

    if not row or not _verify_password(password, row["password_hash"]):
        raise ValueError("Неверный email или пароль.")

    profile = read_profile(int(row["id"]))
    token = _create_session(int(row["id"]))
    return AuthResponse(
        token=token,
        user=_to_user(row),
        profile=ProfileSnapshot(**profile),
    )


def get_user_by_token(token: str) -> User:
    row = fetch_one(
        """
        SELECT users.id, users.email
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
        """,
        (token,),
    )
    if not row:
        raise ValueError("Сессия не найдена.")

    return _to_user(row)


def get_profile(user_id: int) -> ProfileSnapshot:
    return ProfileSnapshot(**read_profile(user_id))


def sync_profile(user_id: int, profile: ProfileSnapshot) -> ProfileSnapshot:
    write_profile(
        user_id=user_id,
        saved_playlists=[playlist.model_dump() for playlist in profile.savedPlaylists],
        liked_tracks=[track.model_dump() for track in profile.likedTracks],
    )
    return get_profile(user_id)
