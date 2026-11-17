from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import can_request, current_user, get_db
from app.agent.runner import recommendation_summary
from app.core.metrics import AGENT_CALLS
from app.models.entities import Approval, ApprovalStatus, CapacityRequest, Rack, RequestStatus, Site, User
from app.schemas.approval import ProposalOutput
from app.services.audit import write_audit
from app.services.placement import RackCapacity, best_fit

router = APIRouter(prefix="/agent", tags=["capacity assistant"])


def propose(db: Session, request: CapacityRequest, actor: User) -> Approval:
    racks = list(db.scalars(select(Rack).where(Rack.site_id == request.site_id).order_by(Rack.id)))
    capacities = [RackCapacity(r.id, r.total_slots - r.used_slots) for r in racks]
    allocations = best_fit(request.quantity, capacities)
    if allocations is None:
        raise HTTPException(status_code=409, detail="There is not enough capacity at this site")
    allocation_json = [{"rack_id": item.rack_id, "quantity": item.quantity} for item in allocations]
    summary = recommendation_summary(db, request, allocation_json)
    proposal = {"summary": summary,
                "allocations": allocation_json}
    approval = Approval(request_id=request.id, proposed_by="agent", proposal_json=proposal, status=ApprovalStatus.PENDING)
    request.status = RequestStatus.PROPOSED
    db.add(approval)
    write_audit(db, actor, "agent.propose", "capacity_request", request.id, proposal)
    return approval


@router.post("/requests/{request_id}/propose", response_model=ProposalOutput, status_code=201)
def propose_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(can_request)):
    request = db.scalar(select(CapacityRequest).where(CapacityRequest.id == request_id).with_for_update())
    if request is None:
        AGENT_CALLS.labels("request_not_found").inc()
        write_audit(db, user, "agent.call_failed", "capacity_request", request_id, {"reason": "request_not_found"})
        db.commit()
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != RequestStatus.PENDING:
        AGENT_CALLS.labels("not_pending").inc()
        write_audit(db, user, "agent.call_failed", "capacity_request", request.id, {"reason": "request_not_pending"})
        db.commit()
        raise HTTPException(status_code=409, detail="Request is not pending")
    try:
        approval = propose(db, request, user)
    except HTTPException:
        AGENT_CALLS.labels("no_capacity").inc()
        write_audit(db, user, "agent.call_failed", "capacity_request", request.id, {"reason": "no_capacity"})
        db.commit()
        raise
    AGENT_CALLS.labels("proposed").inc()
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/capacity/{site_id}")
def get_site_capacity(site_id: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    racks = list(db.scalars(select(Rack).where(Rack.site_id == site_id)))
    return {"site_id": site_id, "total_slots": sum(r.total_slots for r in racks), "used_slots": sum(r.used_slots for r in racks), "available_slots": sum(r.total_slots-r.used_slots for r in racks)}


@router.get("/pending")
def list_pending(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    requests = db.scalars(select(CapacityRequest).where(CapacityRequest.status == RequestStatus.PENDING).order_by(CapacityRequest.created_at)).all()
    return [{"id": item.id, "site_id": item.site_id, "quantity": item.quantity, "description": item.description} for item in requests]
