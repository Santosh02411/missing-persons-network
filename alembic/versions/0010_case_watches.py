"""case watches (email subscriptions)

Adds case_watches: a user "watching" a case, so they get an email when its
status changes or a sighting on it is verified (see watch_service).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-09

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_watches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.UniqueConstraint("user_id", "case_id", name="uq_case_watch_user_case"),
    )
    op.create_index("ix_case_watches_user_id", "case_watches", ["user_id"])
    op.create_index("ix_case_watches_case_id", "case_watches", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_watches_case_id", table_name="case_watches")
    op.drop_index("ix_case_watches_user_id", table_name="case_watches")
    op.drop_table("case_watches")
