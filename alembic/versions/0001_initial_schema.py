"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-27

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # NOTE: these ENUM objects are defined here but deliberately NOT created
    # manually (no .create() call). When used as a column type inside
    # op.create_table() below, SQLAlchemy automatically creates the
    # corresponding Postgres type as part of creating that table. Calling
    # .create() here AND relying on that automatic creation both try to
    # create the same type, and the second one fails with "already exists" --
    # that was a real bug in an earlier version of this migration.
    user_role = postgresql.ENUM("reporter", "authority", "admin", name="user_role")
    case_status = postgresql.ENUM("open", "lead_found", "resolved", name="case_status")
    sighting_status = postgresql.ENUM(
        "pending", "verified", "dismissed", name="sighting_status"
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="reporter"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_name", sa.String(255), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("age_at_disappearance", sa.Integer(), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("last_seen_location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("last_seen_address", sa.String(500), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", case_status, nullable=False, server_default="open"),
        sa.Column("assigned_authority_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "sightings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("reported_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("address_text", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("status", sighting_status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sightings_case_id", "sightings", ["case_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("log_metadata", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_index("ix_sightings_case_id", table_name="sightings")
    op.drop_table("sightings")
    op.drop_table("cases")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    # NOTE: no manual DROP TYPE calls here either -- dropping each table
    # above automatically drops its enum column's type too (the symmetric
    # counterpart of the automatic creation in upgrade()). Manually dropping
    # them again here would fail with "type does not exist" for the same
    # reason the old upgrade() failed with "already exists".
    op.execute("DROP EXTENSION IF EXISTS postgis")