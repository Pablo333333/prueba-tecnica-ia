from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    name: str
    status: str
    details: str | None = None


class FileUploadResponse(BaseModel):
    file_id: int
    s3_key: str
    stored_rows: int
    uploaded_at: datetime
    validations: list[ValidationResult]
    ai_summary: str | None = None


class FileUploadRequestMeta(BaseModel):
    param_a: str = Field(..., max_length=255)
    param_b: str = Field(..., max_length=255)
    extra: dict[str, Any] | None = None



