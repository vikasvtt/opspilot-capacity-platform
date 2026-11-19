"""Create a small, repeatable dataset for the hosted demo."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.entities import (
    Approval,
    ApprovalStatus,
    AuditLog,
    CapacityRequest,
    Rack,
    RequestStatus,
    Server,
    Site,
    User,
    UserRole,
)


SITE_DATA = (
    ("Hyderabad DC", "Hyderabad", (("HYD-R01", 20, 8), ("HYD-R02", 18, 5), ("HYD-R03", 16, 12), ("HYD-R04", 14, 3))),
    ("Bengaluru DC", "Bengaluru", (("BLR-R01", 22, 10), ("BLR-R02", 18, 6), ("BLR-R03", 16, 9), ("BLR-R04", 14, 2))),
    ("Pune DC", "Pune", (("PUN-R01", 20, 7), ("PUN-R02", 18, 11), ("PUN-R03", 16, 4), ("PUN-R04", 14, 1))),
)

REQUEST_DATA = (
    ("pending-hyd-analytics", "Hyderabad DC", 3, RequestStatus.PENDING, None, "Analytics batch workers"),
    ("pending-blr-build", "Bengaluru DC", 2, RequestStatus.PENDING, None, "CI build agents"),
    ("proposed-hyd-api", "Hyderabad DC", 4, RequestStatus.PROPOSED, ApprovalStatus.PENDING, "API performance test pool"),
    ("proposed-pun-ml", "Pune DC", 3, RequestStatus.PROPOSED, ApprovalStatus.PENDING, "ML inference staging"),
    ("approved-blr-cache", "Bengaluru DC", 2, RequestStatus.APPROVED, ApprovalStatus.APPROVED, "Cache cluster expansion"),
    ("rejected-pun-legacy", "Pune DC", 5, RequestStatus.REJECTED, ApprovalStatus.REJECTED, "Legacy workload migration"),
)


def _ensure_audit(
    db: Session,
    *,
    seed_key: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int,
    details: dict,
) -> None:
    existing = db.scalars(
        select(AuditLog).where(
            AuditLog.actor == actor,
            AuditLog.action == action,
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
    )
    if any(item.details_json.get("seed_key") == seed_key for item in existing):
        return
    db.add(AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details_json={"seed_key": seed_key, **details},
    ))


def seed_demo_data(db: Session, *, approver_email: str, approver_password: str,
                   engineer_email: str, engineer_password: str) -> None:
    """Ensure demo sites, racks, requests, approvals and audit events exist."""
    approver = db.scalar(select(User).where(User.email == approver_email.lower()))
    if approver is None:
        approver = User(email=approver_email.lower(), password_hash=hash_password(approver_password), role=UserRole.APPROVER)
        db.add(approver)
        db.flush()
    engineer = db.scalar(select(User).where(User.email == engineer_email.lower()))
    if engineer is None:
        engineer = User(email=engineer_email.lower(), password_hash=hash_password(engineer_password), role=UserRole.ENGINEER)
        db.add(engineer)
        db.flush()

    sites: dict[str, Site] = {}
    racks_by_name: dict[str, Rack] = {}
    for name, city, rack_data in SITE_DATA:
        total_capacity = sum(total for _, total, _ in rack_data)
        site = db.scalar(select(Site).where(Site.name == name))
        if site is None:
            site = Site(name=name, city=city, total_capacity=total_capacity)
            db.add(site)
            db.flush()
        sites[name] = site
        _ensure_audit(db, seed_key=f"site:{name}", actor=engineer.email,
                      action="inventory.site_created", entity_type="site", entity_id=site.id,
                      details={"name": name, "city": city, "total_capacity": total_capacity})

        for rack_name, slots, base_used in rack_data:
            rack = db.scalar(select(Rack).where(Rack.site_id == site.id, Rack.name == rack_name))
            if rack is None:
                rack = Rack(site_id=site.id, name=rack_name, total_slots=slots, used_slots=base_used)
                db.add(rack)
                db.flush()
            # Keep every occupied slot represented by an inventory server row.
            existing_demo_servers = list(db.scalars(select(Server).where(Server.hostname.like(f"demo-{rack_name.lower()}-%"))))
            for index in range(len(existing_demo_servers) + 1, base_used + 1):
                db.add(Server(rack_id=rack.id, hostname=f"demo-{rack_name.lower()}-{index:02d}"))
            rack.used_slots = max(rack.used_slots, base_used)
            racks_by_name[rack_name] = rack
            _ensure_audit(db, seed_key=f"rack:{rack_name}", actor=engineer.email,
                          action="inventory.rack_created", entity_type="rack", entity_id=rack.id,
                          details={"site_id": site.id, "name": rack_name, "total_slots": slots})

    db.flush()
    for key, site_name, quantity, status, approval_status, description in REQUEST_DATA:
        request_description = f"[OpsPilot demo:{key}] {description}"
        request = db.scalar(select(CapacityRequest).where(CapacityRequest.description == request_description))
        if request is None:
            request = CapacityRequest(
                requested_by=engineer.id,
                site_id=sites[site_name].id,
                quantity=quantity,
                description=request_description,
                status=status,
            )
            db.add(request)
            db.flush()
        _ensure_audit(db, seed_key=f"request:{key}", actor=engineer.email,
                      action="capacity_request.created", entity_type="capacity_request", entity_id=request.id,
                      details={"site_id": request.site_id, "quantity": quantity, "description": description})

        if approval_status is None:
            continue
        approval = db.scalar(select(Approval).where(Approval.request_id == request.id))
        if approval is None:
            site_racks = [rack for rack in racks_by_name.values() if rack.site_id == request.site_id]
            # Choose one rack with enough free room for a clear sample recommendation.
            rack = next(r for r in site_racks if r.total_slots - r.used_slots >= quantity)
            approval = Approval(
                request_id=request.id,
                proposed_by="agent",
                proposal_json={
                    "summary": f"Best-fit demo recommendation: place {quantity} servers in {rack.name}.",
                    "allocations": [{"rack_id": rack.id, "quantity": quantity}],
                },
                status=approval_status,
            )
            if approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
                approval.reviewed_by = approver.id
                approval.reviewed_at = datetime.now(timezone.utc)
                approval.reason = "Seeded sample decision for the demo."
            db.add(approval)
            db.flush()
            if approval_status == ApprovalStatus.APPROVED:
                for index in range(1, quantity + 1):
                    hostname = f"demo-approved-{key}-{index:02d}"
                    if db.scalar(select(Server).where(Server.hostname == hostname)) is None:
                        db.add(Server(rack_id=rack.id, hostname=hostname))
                        rack.used_slots += 1
        _ensure_audit(db, seed_key=f"proposal:{key}", actor=engineer.email,
                      action="agent.propose", entity_type="capacity_request", entity_id=request.id,
                      details={"approval_id": approval.id, "status": status.value})
        if approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
            decision = approval_status.value.lower()
            _ensure_audit(db, seed_key=f"decision:{key}", actor=approver.email,
                          action=f"approval.{decision}", entity_type="approval", entity_id=approval.id,
                          details={"request_id": request.id, "reason": approval.reason})

    db.commit()
