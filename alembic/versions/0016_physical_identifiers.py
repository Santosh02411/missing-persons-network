"""age-progressed photo, physical identifiers, and expanded search

Adds:
  - cases.age_progressed_photo_url / age_progression_note -- an optional
    second photo showing an age-progressed likeness, for long-open cases
    (especially children) where appearance has likely changed.
  - cases.height_cm, eye_color, hair_color, blood_type, distinguishing_marks,
    medical_conditions -- structured physical identifiers, the kind of
    detail real forensic matches are often made from.

Also drops and recreates cases.search_vector (a generated column can't have
its expression altered in place in Postgres) so it also indexes
distinguishing_marks -- see Case.SEARCH_VECTOR_EXPRESSION, which this
migration must stay byte-for-byte identical to.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-11

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

SEARCH_VECTOR_EXPRESSION = (
    "to_tsvector('english', "
    "coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(last_seen_address, '') "
    "|| ' ' || coalesce(distinguishing_marks, ''))"
)


def upgrade() -> None:
    op.add_column("cases", sa.Column("age_progressed_photo_url", sa.String(500), nullable=True))
    op.add_column("cases", sa.Column("age_progression_note", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("height_cm", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("eye_color", sa.String(30), nullable=True))
    op.add_column("cases", sa.Column("hair_color", sa.String(30), nullable=True))
    op.add_column("cases", sa.Column("blood_type", sa.String(10), nullable=True))
    op.add_column("cases", sa.Column("distinguishing_marks", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("medical_conditions", sa.Text(), nullable=True))

    op.execute("DROP INDEX IF EXISTS ix_cases_search_vector")
    op.drop_column("cases", "search_vector")
    op.add_column(
        "cases",
        sa.Column(
            "search_vector",
            TSVECTOR,
            sa.Computed(SEARCH_VECTOR_EXPRESSION, persisted=True),
            nullable=True,
        ),
    )
    op.execute("CREATE INDEX ix_cases_search_vector ON cases USING GIN (search_vector)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cases_search_vector")
    op.drop_column("cases", "search_vector")
    op.add_column(
        "cases",
        sa.Column(
            "search_vector",
            TSVECTOR,
            sa.Computed(
                "to_tsvector('english', "
                "coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(last_seen_address, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.execute("CREATE INDEX ix_cases_search_vector ON cases USING GIN (search_vector)")

    op.drop_column("cases", "medical_conditions")
    op.drop_column("cases", "distinguishing_marks")
    op.drop_column("cases", "blood_type")
    op.drop_column("cases", "hair_color")
    op.drop_column("cases", "eye_color")
    op.drop_column("cases", "height_cm")
    op.drop_column("cases", "age_progression_note")
    op.drop_column("cases", "age_progressed_photo_url")
