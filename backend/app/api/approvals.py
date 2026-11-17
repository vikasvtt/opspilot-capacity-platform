from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import can_approve, get_db
from app.core.metrics import APPROVAL_DECISIONS
from app.models.entities import Approval, ApprovalStatus, CapacityRequest, Rack, RequestStatus, Server, User
from app.schemas.approval import ProposalOutput, ReviewInput
from app.services.audit import write_audit

router = APIRouter(prefix="/approvals", tags=["human approvals"])


@router.get("", response_model=list[ProposalOutput])
def list_approvals(status_filter: ApprovalStatus | None = ApprovalStatus.PENDING, db: Session = Depends(get_db), _user: User = Depends(can_approve)):
    query = select(Approval).order_by(Approval.created_at.desc())
    if status_filter is not None:
        query = query.where(Approval.status == status_filter)
    return list(db.scalars(query))


@router.post("/{approval_id}/review", response_model=ProposalOutput)
def review(approval_id: int, payload: ReviewInput, db: Session = Depends(get_db), user: User = Depends(can_approve)):
    approval = db.scalar(select(Approval).where(Approval.id == approval_id).with_for_update())
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="This proposal has already been reviewed")
    request = db.scalar(select(CapacityRequest).where(CapacityRequest.id == approval.request_id).with_for_update())
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    now = datetime.now(timezone.utc)
    approval.reviewed_by = user.id
    approval.reviewed_at = now
    approval.reason = payload.reason
    if payload.decision == "approve":
        for allocation in approval.proposal_json["allocations"]:
            rack = db.scalar(select(Rack).where(Rack.id == allocation["rack_id"]).with_for_update())
            amount = allocation["quantity"]
            if rack is None or rack.total_slots - rack.used_slots < amount:
                db.rollback()
                raise HTTPException(status_code=409, detail="The proposed capacity is no longer available")
            rack.used_slots += amount
            for _ in range(amount):
                db.add(Server(rack_id=rack.id, hostname=f"opspilot-{request.id}-{uuid4().hex[:10]}"))
        approval.status = ApprovalStatus.APPROVED
        request.status = RequestStatus.APPROVED
    else:
        approval.status = ApprovalStatus.REJECTED
        request.status = RequestStatus.REJECTED
    APPROVAL_DECISIONS.labels(payload.decision).inc()
    write_audit(db, user, f"approval.{payload.decision}", "approval", approval.id, {"request_id": request.id, "reason": payload.reason})
    db.commit()
    db.refresh(approval)
    return approval
