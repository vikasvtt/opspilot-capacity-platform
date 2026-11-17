from app.models.entities import AuditLog, User
from sqlalchemy.orm import Session


def write_audit(db: Session, actor: User | str, action: str, entity_type: str, entity_id: int, details: dict | None = None) -> None:
    name = actor.email if isinstance(actor, User) else actor
    db.add(AuditLog(actor=name, action=action, entity_type=entity_type, entity_id=entity_id, details_json=details or {}))
