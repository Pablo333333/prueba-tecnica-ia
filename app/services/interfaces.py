"""Protocolos que definen los contratos de los servicios de análisis."""

from __future__ import annotations

from typing import Protocol

from app.models.document import DocumentAnalysis
from app.schemas.documents import DocumentAnalysisResult, FacturaData, InformacionData


class StorageServiceProtocol(Protocol):
    """Contrato mínimo para subir archivos a un backend de almacenamiento."""

    def upload(self, *, content: bytes, filename: str, prefix: str = "uploads") -> str: ...


class TextExtractorProtocol(Protocol):
    """Extrae texto plano a partir de un archivo binario."""

    def extract(self, filename: str, content: bytes) -> str: ...


class DocumentClassifierProtocol(Protocol):
    """Determina el tipo de documento basado en su texto."""

    def classify(self, text: str) -> str: ...


class InvoiceParserProtocol(Protocol):
    """Convierte texto plano en una representación estructurada de factura."""

    def parse(self, text: str) -> FacturaData: ...


class InformationAnalyzerProtocol(Protocol):
    """Genera resumen y sentimiento para documentos informativos."""

    def analyze(self, text: str) -> InformacionData: ...


class DocumentRepositoryProtocol(Protocol):
    """Persistencia de resultados de análisis."""

    def save_analysis(
        self,
        *,
        filename: str,
        document_type: str,
        s3_key: str | None,
        payload: DocumentAnalysisResult,
        ai_summary: str | None,
        sentiment: str | None,
    ) -> DocumentAnalysis: ...

