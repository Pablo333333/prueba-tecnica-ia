from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user_id = str(uuid4())
    role = payload.rol
    expires_delta = timedelta(minutes=settings.jwt_exp_minutes)
    access_token = create_access_token(
        {
            "sub": user_id,
            "id_usuario": user_id,
            "role": role,
            "rol": role,
        },
        expires_delta=expires_delta,
    )
    return TokenResponse(
        access_token=access_token,
        expires_at=datetime.now(timezone.utc) + expires_delta,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(user: dict = Depends(get_current_user)) -> TokenResponse:
    extra_minutes = settings.jwt_refresh_extension_minutes
    expires_delta = timedelta(minutes=settings.jwt_exp_minutes + extra_minutes)
    access_token = create_access_token(
        {
            "sub": user.get("sub") or user.get("id_usuario"),
            "id_usuario": user.get("id_usuario") or user.get("sub"),
            "role": user.get("role") or user.get("rol"),
            "rol": user.get("rol") or user.get("role"),
        },
        expires_delta=expires_delta,
    )
    return TokenResponse(
        access_token=access_token,
        expires_at=datetime.now(timezone.utc) + expires_delta,
    )


