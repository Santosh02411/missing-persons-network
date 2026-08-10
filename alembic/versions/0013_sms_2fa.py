"""sms-based two-factor auth

Adds users.phone_number (nullable, only set once SMS OTP setup is
confirmed) and users.sms_otp_enabled (mirrors email_otp_enabled).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-10

"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(32), nullable=True))
    op.add_column(
        "users",
        sa.Column("sms_otp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "sms_otp_enabled")
    op.drop_column("users", "phone_number")
