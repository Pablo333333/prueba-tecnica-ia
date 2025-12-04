import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.time_utils import to_local_datetime
from app.models.upload import UploadedFile, UploadedRow
from app.schemas.files import FileUploadResponse, ValidationResult
from app.services.ai import AIInsightsService
from app.services.storage import S3StorageService
from app.services.validation import ValidationService, parse_csv

router = APIRouter(prefix="/files", tags=["files"])

storage_service = S3StorageService()
validation_service = ValidationService()
ai_service = AIInsightsService()


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    param_a: str = Form(...),
    param_b: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("data_uploader")),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    raw_content = await file.read()
    if not raw_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo vacío")

    try:
        s3_key = storage_service.upload(content=raw_content, filename=file.filename)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    decoded_content = raw_content.decode("utf-8-sig")
    rows = parse_csv(decoded_content)
    validations = validation_service.run_all(rows)

    if any(item["status"] == "ERROR" for item in validations):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"validations": validations},
        )

    uploader_id = user.get("id_usuario") or user.get("sub")
    role = user.get("rol") or user.get("role")

    uploaded_file = UploadedFile(
        original_filename=file.filename,
        uploader_id=uploader_id,
        role=role,
        param_a=param_a,
        param_b=param_b,
        s3_key=s3_key,
        created_at=datetime.utcnow(),
    )
    db.add(uploaded_file)
    db.flush()

    for idx, row in enumerate(rows, start=1):
        db.add(
            UploadedRow(
                file_id=uploaded_file.id,
                row_index=idx,
                data=json.dumps(row, ensure_ascii=False),
            )
        )

    ai_summary = ai_service.summarize_validations(validations=validations, sample_rows=rows)
    uploaded_file.ai_summary = ai_summary

    db.commit()
    db.refresh(uploaded_file)

    return FileUploadResponse(
        file_id=uploaded_file.id,
        s3_key=s3_key,
        stored_rows=len(rows),
        uploaded_at=to_local_datetime(uploaded_file.created_at),
        validations=[ValidationResult(**item) for item in validations],
        ai_summary=ai_summary,
    )


