"""geofenced alert opt-in

Adds users.alerts_enabled / alert_location / alert_radius_km -- opt-in
subscription to geofenced alerts an authority/NGO can push for a newly-
filed case near a location the user cares about (see alert_service).
Off/null by default; nothing changes for existing accounts until they
explicitly opt in.

(Case reopening and sighting-credibility, the other two features landing
in this same batch, needed no schema changes -- reopening reuses the
existing cases.status/audit_logs, and reporter stats are computed from the
existing sightings table.)

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-11

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column(
            "alert_location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )
    op.add_column("users", sa.Column("alert_radius_km", sa.Float(), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_alert_location "
        "ON users USING GIST (alert_location)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_alert_location")
    op.drop_column("users", "alert_radius_km")
    op.drop_column("users", "alert_location")
    op.drop_column("users", "alerts_enabled")
