from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import can_manage_inventory, current_user, get_db
from app.models.entities import Rack, Server, Site, User
from app.services.audit import write_audit
from app.schemas.inventory import RackInput, RackOutput, RackUpdate, ServerInput, ServerOutput, ServerUpdate, SiteInput, SiteOutput, SiteUpdate

router = APIRouter(tags=["inventory"])


@router.get("/sites", response_model=list[SiteOutput])
def list_sites(city: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), sort_by: str = Query("name", pattern="^(name|city|created_at)$"), db: Session = Depends(get_db), _user: User = Depends(current_user)):
    query = select(Site)
    if city:
        query = query.where(Site.city.ilike(f"%{city}%"))
    return list(db.scalars(query.order_by(getattr(Site, sort_by)).offset(offset).limit(limit)))


@router.post("/sites", response_model=SiteOutput, status_code=201)
def create_site(payload: SiteInput, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    site = Site(**payload.model_dump())
    db.add(site)
    try:
        db.flush()
        write_audit(db, user, "inventory.site_created", "site", site.id, payload.model_dump())
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create site")
    db.refresh(site)
    return site


@router.get("/racks", response_model=list[RackOutput])
def list_racks(site_id: int | None = None, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    query = select(Rack).order_by(Rack.site_id, Rack.name)
    if site_id is not None:
        query = query.where(Rack.site_id == site_id)
    return list(db.scalars(query))


@router.post("/racks", response_model=RackOutput, status_code=201)
def create_rack(payload: RackInput, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    if db.get(Site, payload.site_id) is None:
        raise HTTPException(status_code=404, detail="Site not found")
    rack = Rack(**payload.model_dump())
    db.add(rack)
    db.flush()
    write_audit(db, user, "inventory.rack_created", "rack", rack.id, payload.model_dump())
    db.commit()
    db.refresh(rack)
    return rack


@router.get("/servers", response_model=list[ServerOutput])
def list_servers(rack_id: int | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _user: User = Depends(current_user)):
    query = select(Server).order_by(Server.hostname).offset(offset).limit(limit)
    if rack_id is not None:
        query = query.where(Server.rack_id == rack_id)
    return list(db.scalars(query))


@router.post("/servers", response_model=ServerOutput, status_code=201)
def create_server(payload: ServerInput, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    rack = db.scalar(select(Rack).where(Rack.id == payload.rack_id).with_for_update())
    if rack is None:
        raise HTTPException(status_code=404, detail="Rack not found")
    if rack.used_slots >= rack.total_slots:
        raise HTTPException(status_code=409, detail="Rack has no available capacity")
    server = Server(**payload.model_dump())
    rack.used_slots += 1
    db.add(server)
    try:
        db.flush()
        write_audit(db, user, "inventory.server_created", "server", server.id, payload.model_dump())
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not add server")
    db.refresh(server)
    return server


@router.patch("/sites/{site_id}", response_model=SiteOutput)
def update_site(site_id: int, payload: SiteUpdate, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Updated values cannot be null")
    for key, value in changes.items():
        setattr(site, key, value)
    write_audit(db, user, "inventory.site_updated", "site", site.id, changes)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    try:
        write_audit(db, user, "inventory.site_deleted", "site", site.id, {"name": site.name})
        db.delete(site)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Site is still referenced by capacity requests")


@router.patch("/racks/{rack_id}", response_model=RackOutput)
def update_rack(rack_id: int, payload: RackUpdate, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    rack = db.scalar(select(Rack).where(Rack.id == rack_id).with_for_update())
    if rack is None:
        raise HTTPException(status_code=404, detail="Rack not found")
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Updated values cannot be null")
    if changes.get("total_slots", rack.total_slots) < rack.used_slots:
        raise HTTPException(status_code=409, detail="Rack capacity cannot be less than occupied slots")
    for key, value in changes.items():
        setattr(rack, key, value)
    write_audit(db, user, "inventory.rack_updated", "rack", rack.id, changes)
    db.commit()
    db.refresh(rack)
    return rack


@router.delete("/racks/{rack_id}", status_code=204)
def delete_rack(rack_id: int, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    rack = db.get(Rack, rack_id)
    if rack is None:
        raise HTTPException(status_code=404, detail="Rack not found")
    write_audit(db, user, "inventory.rack_deleted", "rack", rack.id, {"name": rack.name})
    db.delete(rack)
    db.commit()


@router.patch("/servers/{server_id}", response_model=ServerOutput)
def update_server(server_id: int, payload: ServerUpdate, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    server.status = payload.status
    write_audit(db, user, "inventory.server_updated", "server", server.id, {"status": payload.status})
    db.commit()
    db.refresh(server)
    return server


@router.delete("/servers/{server_id}", status_code=204)
def delete_server(server_id: int, db: Session = Depends(get_db), user: User = Depends(can_manage_inventory)):
    server = db.scalar(select(Server).where(Server.id == server_id).with_for_update())
    if server is None:
        raise HTTPException(status_code=404, detail="Server not found")
    rack = db.scalar(select(Rack).where(Rack.id == server.rack_id).with_for_update())
    if rack is not None:
        rack.used_slots = max(0, rack.used_slots - 1)
    write_audit(db, user, "inventory.server_deleted", "server", server.id, {"hostname": server.hostname})
    db.delete(server)
    db.commit()
