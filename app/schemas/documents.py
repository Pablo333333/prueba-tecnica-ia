from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel


class PartyInfo(BaseModel):
    nombre: str | None = None
    direccion: str | None = None


class ProductoItem(BaseModel):
    cantidad: float | None = None
    nombre: str | None = None
    precio_unitario: float | None = None
    total: float | None = None


class FacturaData(BaseModel):
    cliente: PartyInfo | None = None
    proveedor: PartyInfo | None = None
    numero: str | None = None
    fecha: str | None = None
    productos: List[ProductoItem] = []
    total: float | None = None


class InformacionData(BaseModel):
    descripcion: str
    resumen: str
    sentimiento: Literal["positivo", "negativo", "neutral"]


class DocumentAnalysisResult(BaseModel):
    document_type: Literal["FACTURA", "INFORMACION"]
    factura: FacturaData | None = None
    informacion: InformacionData | None = None
    raw_text: str


class DocumentAnalysisResponse(BaseModel):
    document_id: int
    s3_key: str | None = None
    result: DocumentAnalysisResult
    created_at: datetime


class EventLogItem(BaseModel):
    id: int
    event_type: str
    description: str
    metadata: dict | None = None
    created_at: datetime




