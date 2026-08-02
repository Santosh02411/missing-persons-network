import enum
import uuid

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    LEAD_FOUND = "lead_found"
    RESOLVED = "resolved"


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
        default=CaseStatus.OPEN,
        nullable=False,
    )

    assigned_authority_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    reporter = relationship("User", back_populates="cases_reported", foreign_keys=[created_by])
    assigned_authority = relationship("User", foreign_keys=[assigned_authority_id])
    sightings = relationship("Sighting", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Case {self.name} ({self.status})>"
