"""Enforce capacity checks and align names from the original local schema."""

from alembic import op
import sqlalchemy as sa

revision = "0002_capacity_checks"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

CONSTRAINT_RENAMES = {
    "users": {
        "unique": {"users_email_key": "uq_users_email"},
        "foreign": {},
    },
    "sites": {
        "unique": {"sites_name_key": "uq_sites_name"},
        "foreign": {},
    },
    "racks": {
        "unique": {},
        "foreign": {"racks_site_id_fkey": "fk_racks_site_id_sites"},
    },
    "servers": {
        "unique": {"servers_hostname_key": "uq_servers_hostname"},
        "foreign": {"servers_rack_id_fkey": "fk_servers_rack_id_racks"},
    },
    "capacity_requests": {
        "unique": {},
        "foreign": {
            "capacity_requests_requested_by_fkey": "fk_capacity_requests_requested_by_users",
            "capacity_requests_site_id_fkey": "fk_capacity_requests_site_id_sites",
        },
    },
    "approvals": {
        "unique": {},
        "foreign": {
            "approvals_request_id_fkey": "fk_approvals_request_id_capacity_requests",
            "approvals_reviewed_by_fkey": "fk_approvals_reviewed_by_users",
        },
    },
}


def _rename_legacy_constraints() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, groups in CONSTRAINT_RENAMES.items():
        unique_names = {item["name"] for item in inspector.get_unique_constraints(table)}
        foreign_names = {item["name"] for item in inspector.get_foreign_keys(table)}
        for old, new in groups["unique"].items():
            if old in unique_names and new not in unique_names:
                op.execute(sa.text(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old}" TO "{new}"'))
        for old, new in groups["foreign"].items():
            if old in foreign_names and new not in foreign_names:
                op.execute(sa.text(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old}" TO "{new}"'))

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("users")}
    if "ix_users_email" in indexes:
        op.drop_index("ix_users_email", table_name="users")


def upgrade() -> None:
    _rename_legacy_constraints()
    op.create_check_constraint("ck_sites_site_capacity_positive", "sites", sa.text("total_capacity > 0"))
    op.create_check_constraint("ck_racks_rack_total_slots_positive", "racks", sa.text("total_slots > 0"))
    op.create_check_constraint(
        "ck_racks_rack_used_slots_in_range",
        "racks",
        sa.text("used_slots >= 0 AND used_slots <= total_slots"),
    )
    op.create_check_constraint(
        "ck_capacity_requests_request_quantity_positive",
        "capacity_requests",
        sa.text("quantity > 0"),
    )


def downgrade() -> None:
    op.drop_constraint("ck_capacity_requests_request_quantity_positive", "capacity_requests", type_="check")
    op.drop_constraint("ck_racks_rack_used_slots_in_range", "racks", type_="check")
    op.drop_constraint("ck_racks_rack_total_slots_positive", "racks", type_="check")
    op.drop_constraint("ck_sites_site_capacity_positive", "sites", type_="check")
