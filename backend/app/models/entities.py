from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(StrEnum):
    VIEWER = "viewer"
    ENGINEER = "engineer"
    APPROVER = "approver"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role", values_callable=lambda enum_cls: [item.value for item in enum_cls]), default=UserRole.VIEWER, nullable=False)


class Site(TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (CheckConstraint("total_capacity > 0", name="site_capacity_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    total_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    racks: Mapped[list["Rack"]] = relationship(back_populates="site", cascade="all, delete-orphan")


class Rack(TimestampMixin, Base):
    __tablename__ = "racks"
    __table_args__ = (CheckConstraint("total_slots > 0", name="rack_total_slots_positive"), CheckConstraint("used_slots >= 0 AND used_slots <= total_slots", name="rack_used_slots_in_range"))
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    total_slots: Mapped[int] = mapped_column(Integer, nullable=False)
    used_slots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    site: Mapped[Site] = relationship(back_populates="racks")
    servers: Mapped[list["Server"]] = relationship(back_populates="rack", cascade="all, delete-orphan")


class Server(TimestampMixin, Base):
    __tablename__ = "servers"
    id: Mapped[int] = mapped_column(primary_key=True)
    rack_id: Mapped[int] = mapped_column(ForeignKey("racks.id", ondelete="CASCADE"), index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    rack: Mapped[Rack] = relationship(back_populates="servers")


class CapacityRequest(TimestampMixin, Base):
    __tablename__ = "capacity_requests"
    __table_args__ = (CheckConstraint("quantity > 0", name="request_quantity_positive"), Index("ix_capacity_requests_status_created_at", "status", "created_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus, name="request_status"), default=RequestStatus.PENDING, nullable=False)


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_status_created_at", "status", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("capacity_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    proposed_by: Mapped[str] = mapped_column(String(16), nullable=False)
    proposal_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, name="approval_status"), default=ApprovalStatus.PENDING, nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(320), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    details_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
