from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import settings

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def create_access_token(subject: str) -> tuple[str, int]:
    lifetime_seconds = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=lifetime_seconds),
        "type": "access",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, lifetime_seconds


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid token type or subject")
    return str(payload["sub"])

