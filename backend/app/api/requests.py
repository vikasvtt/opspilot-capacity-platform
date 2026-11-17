from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import can_request, current_user, get_db
from app.models.entities import CapacityRequest, RequestStatus, Site, User
from app.schemas.inventory import RequestInput, RequestOutput, RequestUpdate
from app.services.audit import write_audit

router = APIRouter(prefix="/requests", tags=["capacity requests"])


@router.get("", response_model=list[RequestOutput])
def list_requests(status_filter: RequestStatus | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _user: User = Depends(current_user)):
    query = select(CapacityRequest).order_by(CapacityRequest.created_at.desc()).offset(offset).limit(limit)
    if status_filter:
        query = query.where(CapacityRequest.status == status_filter)
    return list(db.scalars(query))


@router.post("", response_model=RequestOutput, status_code=201)
def create_request(payload: RequestInput, db: Session = Depends(get_db), user: User = Depends(can_request)):
    if db.get(Site, payload.site_id) is None:
        raise HTTPException(status_code=404, detail="Site not found")
    item = CapacityRequest(requested_by=user.id, status=RequestStatus.PENDING, **payload.model_dump())
    db.add(item)
    db.flush()
    write_audit(db, user, "capacity_request.created", "capacity_request", item.id, payload.model_dump())
    db.commit()
    db.refresh(item)
    return item


@router.get("/{request_id}", response_model=RequestOutput)
def get_request(request_id: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    item = db.get(CapacityRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return item


@router.patch("/{request_id}", response_model=RequestOutput)
def update_request(request_id: int, payload: RequestUpdate, db: Session = Depends(get_db), user: User = Depends(can_request)):
    item = db.scalar(select(CapacityRequest).where(CapacityRequest.id == request_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if item.status != RequestStatus.PENDING or (item.requested_by != user.id and user.role.value != "approver"):
        raise HTTPException(status_code=403, detail="Only the request owner can edit a pending request")
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Updated values cannot be null")
    if "site_id" in changes and db.get(Site, changes["site_id"]) is None:
        raise HTTPException(status_code=404, detail="Site not found")
    for key, value in changes.items():
        setattr(item, key, value)
    write_audit(db, user, "capacity_request.updated", "capacity_request", item.id, changes)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{request_id}", status_code=204)
def delete_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(can_request)):
    item = db.scalar(select(CapacityRequest).where(CapacityRequest.id == request_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if item.status != RequestStatus.PENDING or (item.requested_by != user.id and user.role.value != "approver"):
        raise HTTPException(status_code=403, detail="Only the owner can delete a pending request")
    write_audit(db, user, "capacity_request.deleted", "capacity_request", item.id, {"quantity": item.quantity})
    db.delete(item)
    db.commit()
