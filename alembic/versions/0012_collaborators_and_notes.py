"""case collaborators + private case notes

Adds:
  - case_collaborators: additional authority/NGO accounts given the same
    access as a case's primary assigned_authority (multi-authority
    collaboration on one case).
  - case_notes: private, append-only investigation-log entries, visible
    only to whoever has case access (assigned authority, a collaborator, or
    an admin) -- never the reporter or the public.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-09

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_collaborators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_collaborator_case_user"),
    )
    op.create_index("ix_case_collaborators_case_id", "case_collaborators", ["case_id"])
    op.create_index("ix_case_collaborators_user_id", "case_collaborators", ["user_id"])

    op.create_table(
        "case_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
    )
    op.create_index("ix_case_notes_case_id", "case_notes", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_notes_case_id", table_name="case_notes")
    op.drop_table("case_notes")

    op.drop_index("ix_case_collaborators_user_id", table_name="case_collaborators")
    op.drop_index("ix_case_collaborators_case_id", table_name="case_collaborators")
    op.drop_table("case_collaborators")
