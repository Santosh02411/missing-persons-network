"""authority jurisdiction + case routing to a specific station

Adds:
  - users.jurisdiction_location (geography point, nullable) -- only
    meaningful for AUTHORITY accounts. When set, this is the station's
    location, used to route newly-filed cases to the nearest station
    instead of broadcasting every case to every authority nationwide.
  - cases.target_authority_id -- the specific authority/NGO account a
    case was routed to at filing time (auto-picked nearest, or chosen
    by the reporter). NULL means no jurisdiction-matched station was
    found, so the case falls back to the old "any verified authority
    can see it" behavior -- a resilience backstop, not the common case.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-08

"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "jurisdiction_location",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_jurisdiction_location "
        "ON users USING GIST (jurisdiction_location)"
    )

    op.add_column(
        "cases",
        sa.Column(
            "target_authority_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_cases_target_authority_id", "cases", ["target_authority_id"])


def downgrade() -> None:
    op.drop_index("ix_cases_target_authority_id", table_name="cases")
    op.drop_column("cases", "target_authority_id")

    op.execute("DROP INDEX IF EXISTS idx_users_jurisdiction_location")
    op.drop_column("users", "jurisdiction_location")
