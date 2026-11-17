from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.models.entities import Rack, Site, User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/site-utilization")
def site_utilization(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    total = func.coalesce(func.sum(Rack.total_slots), 0).label("total_slots")
    used = func.coalesce(func.sum(Rack.used_slots), 0).label("used_slots")
    utilization = case((func.coalesce(func.sum(Rack.total_slots), 0) == 0, 0.0), else_=100.0 * func.coalesce(func.sum(Rack.used_slots), 0) / func.sum(Rack.total_slots)).label("utilization_percent")
    rank = func.row_number().over(order_by=utilization.desc()).label("usage_rank")
    rows = db.execute(select(Site.id, Site.name, Site.city, total, used, utilization, rank).outerjoin(Rack, Rack.site_id == Site.id).group_by(Site.id).order_by(utilization.desc(), Site.name)).all()
    return [{"site_id": row.id, "name": row.name, "city": row.city, "total_slots": int(row.total_slots), "used_slots": int(row.used_slots), "available_slots": int(row.total_slots - row.used_slots), "utilization_percent": round(float(row.utilization_percent), 1), "usage_rank": int(row.usage_rank)} for row in rows]
