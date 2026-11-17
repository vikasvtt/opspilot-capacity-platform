from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hash.verify(password, encoded)
    except Exception:
        return False


def create_token(user_id: int, role: str, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "type": token_type, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_token_pair(user_id: int, role: str) -> dict[str, str]:
    return {
        "access_token": create_token(user_id, role, "access", timedelta(minutes=settings.access_token_minutes)),
        "refresh_token": create_token(user_id, role, "refresh", timedelta(days=settings.refresh_token_days)),
    }


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload
