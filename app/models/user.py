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

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.REPORTER, nullable=False
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

    cases_reported = relationship(
        "Case", back_populates="reporter", foreign_keys="Case.created_by"
    )
    sightings_reported = relationship(
        "Sighting", back_populates="reporter", foreign_keys="Sighting.reported_by"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
