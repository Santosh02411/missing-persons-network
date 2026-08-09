import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class SightingStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    DISMISSED = "dismissed"


class Sighting(Base):
    __tablename__ = "sightings"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )

    # Nullable: public can submit anonymous tips without an account
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    address_text: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Face-similarity score (0..1) between this sighting's photo and the
    # case's photo, computed once at submission time -- see
    # face_match_service.match_faces() and sighting_service.create_sighting().
    # NULL (not 0.0) when no score could be computed (missing photo on
    # either side, or no face detected) -- that's a different, weaker signal
    # than "compared and scored low", and authorities reviewing the queue
    # need to be able to tell the two apart.
    photo_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # values_callable required -- see app/models/user.py's role column for
    # the full explanation of why (SQLAlchemy defaults to enum member NAME,
    # not VALUE, which mismatches the lowercase native Postgres enum type).
    status: Mapped[SightingStatus] = mapped_column(
        Enum(SightingStatus, name="sighting_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=SightingStatus.PENDING,
        nullable=False,
    )

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case = relationship("Case", back_populates="sightings")
    reporter = relationship(
        "User", back_populates="sightings_reported", foreign_keys=[reported_by]
    )
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<Sighting case={self.case_id} status={self.status}>"
