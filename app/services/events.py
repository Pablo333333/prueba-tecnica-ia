import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.document import EventLog


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, event_type: str, description: str, metadata: dict | None = None) -> EventLog:
        record = EventLog(
            event_type=event_type,
            description=description,
            extra=json.dumps(metadata or {}, ensure_ascii=False),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list(
        self,
        *,
        event_type: str | None = None,
        description: str | None = None,
        start_date=None,
        end_date=None,
    ):
        query = self.db.query(EventLog)
        if event_type:
            query = query.filter(EventLog.event_type == event_type)
        if description:
            query = query.filter(EventLog.description.ilike(f"%{description}%"))
        if start_date:
            query = query.filter(EventLog.created_at >= start_date)
        if end_date:
            query = query.filter(EventLog.created_at <= end_date)
        return query.order_by(EventLog.created_at.desc()).all()

