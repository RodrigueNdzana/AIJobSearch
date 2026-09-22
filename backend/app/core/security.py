from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


def generate_reset_token() -> tuple[str, str]:
    """
    Returns (raw_token, token_hash). The raw token is emailed to the user and
    never stored; only its SHA-256 hash is persisted, the same principle as a
    password — if the database leaked, stored hashes alone can't be used to
    reset anyone's account.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    return raw_token, token_hash


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
