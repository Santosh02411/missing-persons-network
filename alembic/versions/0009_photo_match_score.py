"""sighting photo match score

Adds sightings.photo_match_score (float, nullable) -- the face-similarity
score (0..1) between the sighting's photo and its case's photo, computed
once at submission time by face_match_service.match_faces(). NULL means no
score is available (no photo on one/both sides, or no face detected in
one/both), which is a distinct, expected outcome from "definitely not a
match" (0.0) -- so it has to stay nullable, not default to 0.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-08

"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sightings", sa.Column("photo_match_score", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sightings", "photo_match_score")
