import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CaseCollaborator(Base):
    """An authority/NGO account given the same access as the case's primary
    assigned_authority -- editing, status changes, sharing, and case notes
    (see case_service.has_case_access, the single check all of those route
    through). Lets a station and an NGO (or two stations) actively work a
    case together instead of only one account ever having write access.

    Distinct from assigned_authority_id on Case (the one account considered
    "primary," e.g. shown as who's handling it) and from target_authority_id
    (routing before the case is even approved) -- this table is purely
    "who else has full access," added after the fact."""

    __tablename__ = "case_collaborators"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_collaborator_case_user"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    added_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    case = relationship("Case")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<CaseCollaborator case={self.case_id} user={self.user_id}>"
