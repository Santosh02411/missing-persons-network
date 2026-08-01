"""add gist spatial indexes for geo-search

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-27

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS matters here: GeoAlchemy2's Geography column type
    # defaults to spatial_index=True, which means it ALREADY auto-created a
    # GIST index (with this exact idx_<table>_<column> naming convention)
    # when migration 0001 created these tables -- a fact this migration
    # didn't originally account for, causing a "relation already exists"
    # error. This migration is now a documented no-op in the common case,
    # and a safety net if that default ever changes.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_last_seen_location "
        "ON cases USING GIST (last_seen_location)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sightings_location "
        "ON sightings USING GIST (location)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sightings_location")
    op.execute("DROP INDEX IF EXISTS idx_cases_last_seen_location")
