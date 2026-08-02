import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    target_type: str
    target_id: uuid.UUID
    log_metadata: dict
    created_at: datetime
