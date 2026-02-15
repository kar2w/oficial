import datetime as dt
import uuid
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_event(
    db: Session,
    *,
    actor: str,
    role: str | None,
    ip: str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditLog:
    ent_uuid: uuid.UUID | None = None
    if entity_id:
        ent_uuid = entity_id if isinstance(entity_id, uuid.UUID) else uuid.UUID(str(entity_id))

    row = AuditLog(
        actor=actor,
        role=role,
        ip=ip,
        action=action,
        entity_type=entity_type,
        entity_id=ent_uuid,
        meta=meta,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def list_audit(
    db: Session,
    *,
    limit: int = 200,
    offset: int = 0,
    actor: str | None = None,
    action: str | None = None,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    where = ["1=1"]

    if actor:
        where.append("actor ILIKE :actor")
        params["actor"] = f"%{actor}%"
    if action:
        where.append("action = :action")
        params["action"] = action
    if date_from:
        where.append("created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("created_at <= :date_to")
        params["date_to"] = date_to

    sql = sa_text(
        f"""
        SELECT id, created_at, actor, role, ip::text AS ip, action, entity_type, entity_id::text AS entity_id, meta
        FROM audit_log
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        OFFSET :offset
        LIMIT :limit
        """
    )

    rows = db.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]
