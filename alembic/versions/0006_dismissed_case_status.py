"""add dismissed case status

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-04

"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE case_status ADD VALUE IF NOT EXISTS 'dismissed'")


def downgrade() -> None:
    # See 0005's downgrade note -- removing an enum value safely requires a
    # full type rebuild; not implemented since nothing currently needs to
    # downgrade past this migration.
    pass
