"""duplicate-case detection on filing

Adds cases.possible_duplicates (JSON, default []) -- a snapshot computed
once at filing time (see duplicate_detection_service) of other cases that
looked similar by name/location/date, for the reviewing authority to see.
Never used to block filing.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-10

"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("possible_duplicates", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("cases", "possible_duplicates")
