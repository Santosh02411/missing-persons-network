import enum
import uuid

from geoalchemy2 import Geography
from sqlalchemy import Computed, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CaseStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"  # just filed, not public yet -- awaiting authority approval
    OPEN = "open"
    LEAD_FOUND = "lead_found"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"  # rejected as invalid/fake, or closed without resolution


# Shared between the model (below, so Base.metadata.create_all() -- what the
# test suite uses -- creates a real generated column, not a plain nullable
# one) and migration 0015 (what a real deployment applies via `alembic
# upgrade head`) -- both need the identical expression, or the two schemas
# drift and only one of them actually works.
SEARCH_VECTOR_EXPRESSION = (
    "to_tsvector('english', "
    "coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(last_seen_address, ''))"
)


class Case(Base):
    __tablename__ = "cases"

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    age_at_disappearance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Free-text, not a DB enum -- deliberately open-ended (not limited to a
    # fixed set) since a missing-persons registry shouldn't force reporters
    # into categories that don't fit. Optional: many reports won't specify
    # it. Used as a search filter (case_service.list_cases), not shown as a
    # primary identifying feature anywhere in the UI.
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Computed once at filing time (see duplicate_detection_service), not
    # re-evaluated later -- a snapshot of what looked like a possible
    # duplicate when this case was created, for the reviewing authority to
    # see during approval. Never used to block filing a case; a real missing
    # person must never be turned away over a name/location match. Empty
    # list (the default), not null, when nothing matched.
    possible_duplicates: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Generated (STORED) by Postgres itself from name + description +
    # last_seen_address -- see SEARCH_VECTOR_EXPRESSION above and migration
    # 0015. Never written to from Python, just queried against in
    # case_service.list_cases() via func.plainto_tsquery/ts_rank.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(SEARCH_VECTOR_EXPRESSION, persisted=True), nullable=True, deferred=True
    )

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
