import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CaseWatch(Base):
    """A user "watching" a case -- they get an email when its status
    changes or a sighting on it is verified (see watch_service.notify_watchers,
    called from case_service and sighting_service). Any authenticated user
    can watch any case they can see; there's no role restriction, since
    following a case you filed or care about isn't an authority action."""

    __tablename__ = "case_watches"
    __table_args__ = (UniqueConstraint("user_id", "case_id", name="uq_case_watch_user_case"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )

    user = relationship("User")
    case = relationship("Case")

    def __repr__(self) -> str:
        return f"<CaseWatch user={self.user_id} case={self.case_id}>"
