"""case gender field (for search filters)

Adds cases.gender -- free-text, nullable, not a DB enum (deliberately
open-ended). Used by case_service.list_cases() as an optional search filter
alongside age range, date range, and region.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-09

"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("gender", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("cases", "gender")
