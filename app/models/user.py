import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class UserRole(str, enum.Enum):
    REPORTER = "reporter"      # general public — can file cases & sightings
    AUTHORITY = "authority"    # verified police / NGO account
    ADMIN = "admin"            # super-admin


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # values_callable is required here: SQLAlchemy's Enum type defaults to
    # using the Python enum member's NAME (e.g. "REPORTER") for the database
    # value, not its .value ("reporter") -- even though UserRole inherits
    # from str. Without this, every query filtering/inserting by role sends
    # the wrong case and fails with "invalid input value for enum user_role"
    # against the lowercase values the native Postgres enum type actually
    # has (see migration 0001_initial_schema.py).
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=UserRole.REPORTER,
        nullable=False,
    )

    # Authority accounts require admin approval before they can verify sightings
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Separate from is_verified above (which gates authority permissions) --
    # this tracks whether the account's email address has been confirmed via
    # the emailed verification link. Not used to block login or actions (see
    # docs/SECURITY_AND_ACCESS.md), just surfaced to the frontend so it can
    # nudge an unverified user to confirm their email.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Only meaningful for AUTHORITY role (e.g. "Belagavi City Police", "Missing Children NGO")
    org_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Two-factor auth (TOTP). totp_secret is set (but totp_enabled stays
    # False) while setup is pending confirmation via /auth/2fa/verify --
    # see docs/SECURITY_AND_ACCESS.md for why the secret is stored in
    # plaintext here (a documented tradeoff, not an oversight) and for the
    # decision to gate setup to authority/admin roles only.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Alternative to TOTP -- a fresh code emailed at each login instead of an
    # authenticator app. No secret to store here: each code is generated,
    # emailed, and checked against Redis at login time (see auth_service).
    # Only one of totp_enabled/email_otp_enabled should be true at a time --
    # enforced in auth_service, not at the DB level.
    email_otp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cases_reported = relationship(
        "Case", back_populates="reporter", foreign_keys="Case.created_by"
    )
    sightings_reported = relationship(
        "Sighting", back_populates="reporter", foreign_keys="Sighting.reported_by"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
