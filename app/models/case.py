import enum
import uuid

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CaseStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"  # just filed, not public yet -- awaiting authority approval
    OPEN = "open"
    LEAD_FOUND = "lead_found"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"  # rejected as invalid/fake, or closed without resolution


class Case(Base):
    __tablename__ = "cases"

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    age_at_disappearance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # PostGIS point: SRID 4326 = standard WGS84 lat/lng
    last_seen_location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    last_seen_address: Mapped[str] = mapped_column(String(500), nullable=False)
    last_seen_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)

    # values_callable required -- see app/models/user.py's role column for
    # the full explanation of why (SQLAlchemy defaults to enum member NAME,
    # not VALUE, which mismatches the lowercase native Postgres enum type).
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=CaseStatus.PENDING_REVIEW,
        nullable=False,
    )

    assigned_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # The specific authority/NGO this case was routed to at filing time --
    # either the reporter's explicit choice or the nearest verified station
    # to last_seen_location (see case_service.create_case). Distinct from
    # assigned_authority_id, which is set only once someone actually
    # approves/claims the case. NULL means no jurisdiction-matched station
    # was found, so the case is visible to any verified authority as a
    # fallback (see case_service.list_pending_approval_cases) rather than
    # being stuck unreviewable.
    target_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    reporter = relationship("User", back_populates="cases_reported", foreign_keys=[created_by])
    assigned_authority = relationship("User", foreign_keys=[assigned_authority_id])
    target_authority = relationship("User", foreign_keys=[target_authority_id])
    sightings = relationship("Sighting", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Case {self.name} ({self.status})>"
