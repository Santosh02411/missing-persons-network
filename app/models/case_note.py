import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CaseNote(Base):
    """A private, internal investigation-log entry on a case -- visible only
    to whoever has case access (the assigned authority, any case
    collaborator, or an admin; see case_service.has_case_access), never to
    the reporter or the public. Append-only by design: no update/delete
    endpoint, since an investigation log is a record of what happened and
    when, not a document to be revised."""

    __tablename__ = "case_notes"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    case = relationship("Case")
    author = relationship("User")

    def __repr__(self) -> str:
        return f"<CaseNote case={self.case_id} author={self.author_id}>"
