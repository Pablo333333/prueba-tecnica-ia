import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openpyxl import Workbook

from app.api.deps import get_db, require_roles
from app.core.time_utils import to_local_datetime, local_string_to_utc
from app.models.document import EventLog
from app.schemas.documents import EventLogItem
from app.services.events import EventService

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/events", response_model=list[EventLogItem])
def list_events(
    event_type: str | None = None,
    description: str | None = None,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("data_uploader")),
):
    """Lista eventos históricos con filtros y registra que el usuario los consultó.

    Args:
        event_type (str | None): Tipo de evento a filtrar.
        description (str | None): Texto a buscar en la descripción.
        start_date (str | None): Inicio del rango horario (ISO local).
        end_date (str | None): Fin del rango horario (ISO local).
        db (Session): Sesión de base de datos para leer y registrar eventos.
        user (dict): Payload del usuario autenticado.

    Returns:
        list[EventLogItem]: Eventos encontrados con su metadata parseada.
    """
    start_dt = _parse_local_range(start_date)
    end_dt = _parse_local_range(end_date)
    query = db.query(EventLog)
    if event_type:
        query = query.filter(EventLog.event_type == event_type)
    if description:
        query = query.filter(EventLog.description.ilike(f"%{description}%"))
    if start_dt:
        query = query.filter(EventLog.created_at >= start_dt)
    if end_dt:
        query = query.filter(EventLog.created_at <= end_dt)
    items = query.order_by(EventLog.created_at.desc()).all()
    EventService(db).create(
        event_type="Interacción del usuario",
        description=f"{user.get('id_usuario')} consultó el histórico",
        metadata={
            "filters": {
                "event_type": event_type,
                "description": description,
                "start_date": start_date,
                "end_date": end_date,
            }
        },
    )
    return [
        EventLogItem(
            id=item.id,
            event_type=item.event_type,
            description=item.description,
            metadata=_safe_json(item.extra),
            created_at=to_local_datetime(item.created_at),
        )
        for item in items
    ]


@router.get("/events/export")
def export_events(
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles("data_uploader")),
):
    """Exporta el histórico completo a Excel y registra la acción del usuario.

    Args:
        db (Session): Sesión de base de datos para leer/escribir eventos.
        user (dict): Payload JWT del usuario que exporta.

    Returns:
        StreamingResponse: Archivo XLSX descargable.
    """
    items = db.query(EventLog).order_by(EventLog.created_at.desc()).all()
    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Tipo", "Descripción", "Fecha", "Metadata"])
    for item in items:
        created_at = to_local_datetime(item.created_at)
        ws.append(
            [
                item.id,
                item.event_type,
                item.description,
                created_at.isoformat() if created_at else "",
                item.extra or "",
            ]
        )
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    EventService(db).create(
        event_type="Interacción del usuario",
        description=f"{user.get('id_usuario')} exportó el histórico a Excel",
        metadata={"row_count": len(items)},
    )
    headers = {"Content-Disposition": 'attachment; filename="historial.xlsx"'}
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers
    )


def _safe_json(payload: str | None):
    """Convierte la cadena JSON almacenada o devuelve None si falla."""
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _parse_local_range(raw_value: str | None):
    """Convierte una fecha ISO local a UTC; lanza 400 si es inválida."""
    if not raw_value:
        return None
    try:
        return local_string_to_utc(raw_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use ISO-8601 (YYYY-MM-DDTHH:MM)")

