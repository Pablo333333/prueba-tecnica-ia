from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.db.session import get_db

auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó el token de autenticación",
        )
    return decode_token(credentials.credentials)


def require_roles(*roles: str):
    def _role_guard(user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role") or user.get("rol")
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol sin permisos suficientes",
            )
        return user | {"role": role}

    return _role_guard


__all__ = ["get_current_user", "require_roles", "get_db"]


