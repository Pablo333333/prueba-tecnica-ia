"""Repositorio para persistir resultados del análisis de documentos."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.document import DocumentAnalysis
from app.schemas.documents import DocumentAnalysisResult
from app.services.interfaces import DocumentRepositoryProtocol


class DocumentRepository(DocumentRepositoryProtocol):
    """Implementa la persistencia usando SQLAlchemy."""

    def __init__(self, db: Session):
        """
        Inicializa el repositorio con una sesión de base de datos.

        Args:
            db (Session): Sesión activa conectada a SQL Server.
        """
        self.db = db

    def save_analysis(
        self,
        *,
        filename: str,
        document_type: str,
        s3_key: str | None,
        payload: DocumentAnalysisResult,
        ai_summary: str | None,
        sentiment: str | None,
    ) -> DocumentAnalysis:
        """
        Persiste el resultado del análisis y devuelve el registro creado.

        Args:
            filename (str): Nombre original del archivo.
            document_type (str): Clasificación resultante (FACTURA/INFORMACION).
            s3_key (str | None): Ruta en S3 o None si falló la subida.
            payload (DocumentAnalysisResult): Resultado estructurado del análisis.
            ai_summary (str | None): Resumen generado por IA.
            sentiment (str | None): Sentimiento detectado en el documento.

        Returns:
            DocumentAnalysis: Instancia ORM persistida y refrescada.
        """
        record = DocumentAnalysis(
            filename=filename,
            document_type=document_type,
            s3_key=s3_key,
            extracted_payload=json.dumps(payload.model_dump(), ensure_ascii=False),
            ai_summary=ai_summary,
            sentiment=sentiment,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

