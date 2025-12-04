from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings


class TokenError(HTTPException):
    def __init__(self, detail: str = "Token inválido"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def create_access_token(payload: Dict[str, Any], expires_delta: timedelta | None = None) -> str:
    expires_in = expires_delta or timedelta(minutes=settings.jwt_exp_minutes)
    now = datetime.now(timezone.utc)
    expire = now + expires_in

    to_encode = payload.copy()
    to_encode.update({"exp": expire, "iat": now})
    try:
        return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    except Exception as exc:  # pragma: no cover
        raise TokenError("No se pudo firmar el token") from exc


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError("Token inválido o expirado") from exc



