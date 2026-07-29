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
    # GiST indexes accelerate ST_DWithin/ST_Distance queries used by
    # geo_service.nearby_cases() / nearby_sightings() (see
    # docs/TECHNICAL_ARCHITECTURE.md). Without these, every nearby-search
    # query does a full table scan computing distance for every row.
    op.execute(
        "CREATE INDEX idx_cases_last_seen_location "
        "ON cases USING GIST (last_seen_location)"
    )
    op.execute(
        "CREATE INDEX idx_sightings_location "
        "ON sightings USING GIST (location)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sightings_location")
    op.execute("DROP INDEX IF EXISTS idx_cases_last_seen_location")
