from datetime import datetime
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.time_utils import to_local_datetime
from app.schemas.documents import DocumentAnalysisResponse
from app.services.document_analysis import DocumentAnalyzerService
from app.services.events import EventService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("data_uploader")),
    db: Session = Depends(get_db),
):
    """Analiza un documento PDF/imagen y guarda el resultado estructurado.

    Args:
        file (UploadFile): Documento recibido en la petición.
        user (dict): Usuario autenticado (payload JWT).
        db (Session): Sesión de base de datos para persistir análisis y eventos.

    Returns:
        DocumentAnalysisResponse: Detalle del documento analizado con ID, clave S3 y payload (factura o información).
    """
    if file.content_type not in {"application/pdf", "image/png", "image/jpeg"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten PDF, PNG o JPG",
        )

    content = await file.read()
    analyzer = DocumentAnalyzerService(db)
    event_service = EventService(db)

    result = analyzer.analyze(filename=file.filename, content=content)

    event_service.create(
        event_type="Carga de documento",
        description=f"{user.get('id_usuario')} subió {file.filename}",
        metadata={"document_id": result.record.id},
    )
    event_service.create(
        event_type="IA",
        description=f"Análisis automático del documento {result.record.id}",
        metadata=result.payload.model_dump(),
    )

    return DocumentAnalysisResponse(
        document_id=result.record.id,
        s3_key=result.record.s3_key,
        result=result.payload,
        created_at=to_local_datetime(result.record.created_at),
    )


