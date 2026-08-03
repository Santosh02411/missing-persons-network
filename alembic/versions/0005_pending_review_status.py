"""add pending_review case status

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-02

"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE ... IF NOT EXISTS, and (unlike older
    # versions) permits it inside a transaction as long as the new value
    # isn't used by another statement in that same transaction -- which is
    # the case here, so this is safe as a normal migration.
    op.execute("ALTER TYPE case_status ADD VALUE IF NOT EXISTS 'pending_review'")


def downgrade() -> None:
    # Postgres has no direct "remove enum value" -- doing so safely requires
    # rebuilding the type (rename old, create new without the value, migrate
    # column, drop old). Not implemented here since nothing in this project
    # currently needs to downgrade past this migration; if you do, any rows
    # with status='pending_review' must be reassigned to another status
    # first, or the rebuild will fail.
    pass
