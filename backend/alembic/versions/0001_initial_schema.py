"""Create the initial OpsPilot schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("viewer", "engineer", "approver", name="user_role", create_type=False)
request_status = postgresql.ENUM(
    "PENDING", "PROPOSED", "APPROVED", "REJECTED", "FAILED", name="request_status", create_type=False
)
approval_status = postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="approval_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("viewer", "engineer", "approver", name="user_role").create(bind, checkfirst=True)
    postgresql.ENUM(
        "PENDING", "PROPOSED", "APPROVED", "REJECTED", "FAILED", name="request_status"
    ).create(bind, checkfirst=True)
    postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="approval_status").create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.UniqueConstraint("name", name="uq_sites_name"),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sites_city", "sites", ["city"])

    op.create_table(
        "racks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", name="fk_racks_site_id_sites", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("total_slots", sa.Integer(), nullable=False),
        sa.Column("used_slots", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_racks_site_id", "racks", ["site_id"])

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rack_id", sa.Integer(), sa.ForeignKey("racks.id", name="fk_servers_rack_id_racks", ondelete="CASCADE"), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.UniqueConstraint("hostname", name="uq_servers_hostname"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_servers_rack_id", "servers", ["rack_id"])

    op.create_table(
        "capacity_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", name="fk_capacity_requests_requested_by_users", ondelete="RESTRICT"), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", name="fk_capacity_requests_site_id_sites", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", request_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_capacity_requests_requested_by", "capacity_requests", ["requested_by"])
    op.create_index("ix_capacity_requests_site_id", "capacity_requests", ["site_id"])
    op.create_index("ix_capacity_requests_status_created_at", "capacity_requests", ["status", "created_at"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("capacity_requests.id", name="fk_approvals_request_id_capacity_requests", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_by", sa.String(16), nullable=False),
        sa.Column("proposal_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", approval_status, nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", name="fk_approvals_reviewed_by_users", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approvals_request_id", "approvals", ["request_id"])
    op.create_index("ix_approvals_status_created_at", "approvals", ["status", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(320), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("details_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("approvals")
    op.drop_table("capacity_requests")
    op.drop_table("servers")
    op.drop_table("racks")
    op.drop_table("sites")
    op.drop_table("users")
    approval_status.drop(op.get_bind(), checkfirst=True)
    request_status.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
