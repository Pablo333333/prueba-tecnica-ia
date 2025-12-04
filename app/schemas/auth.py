from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_ROLES = ("data_uploader", "viewer")


class LoginRequest(BaseModel):
    rol: str = Field(..., description="Rol permitido: data_uploader o viewer")

    @field_validator("rol")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ALLOWED_ROLES:
            raise ValueError(f"Rol inválido. Usa uno de: {', '.join(ALLOWED_ROLES)}")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class TokenPayload(BaseModel):
    sub: str
    id_usuario: str
    role: str | None = None
    rol: str
    exp: int


