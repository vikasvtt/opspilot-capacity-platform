from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SiteInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    total_capacity: int = Field(gt=0)


class SiteOutput(SiteInput):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RackInput(BaseModel):
    site_id: int
    name: str = Field(min_length=1, max_length=120)
    total_slots: int = Field(gt=0)


class RackOutput(RackInput):
    id: int
    used_slots: int
    model_config = ConfigDict(from_attributes=True)


class ServerInput(BaseModel):
    rack_id: int
    hostname: str = Field(min_length=1, max_length=255)


class ServerOutput(ServerInput):
    id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RequestInput(BaseModel):
    site_id: int
    quantity: int = Field(gt=0, le=10000)
    description: str = Field(default="", max_length=2000)


class RequestOutput(BaseModel):
    id: int
    requested_by: int
    site_id: int
    quantity: int
    description: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    total_capacity: int | None = Field(default=None, gt=0)


class RackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    total_slots: int | None = Field(default=None, gt=0)


class ServerUpdate(BaseModel):
    status: str = Field(pattern="^(active|maintenance|offline)$")


class RequestUpdate(BaseModel):
    site_id: int | None = None
    quantity: int | None = Field(default=None, gt=0, le=10000)
    description: str | None = Field(default=None, max_length=2000)
