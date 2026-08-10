# Import all models here so Alembic's autogenerate picks them up
# via Base.metadata. Nothing else should import from this module except
# alembic/env.py — application code should import models directly.

from app.db.base_class import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.sighting import Sighting  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.case_watch import CaseWatch  # noqa: F401
from app.models.case_collaborator import CaseCollaborator  # noqa: F401
from app.models.case_note import CaseNote  # noqa: F401
