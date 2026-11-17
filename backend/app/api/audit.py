from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import can_approve, get_db
from app.models.entities import AuditLog, User

router = APIRouter(prefix="/audit", tags=["audit log"])


@router.get("")
def list_audit(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _user: User = Depends(can_approve)):
    entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
    return [{"id": item.id, "actor": item.actor, "action": item.action, "entity_type": item.entity_type, "entity_id": item.entity_id, "details": item.details_json, "created_at": item.created_at} for item in entries]
