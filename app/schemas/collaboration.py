import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CaseNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CaseNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime


class CollaboratorAdd(BaseModel):
    authority_id: uuid.UUID


class CollaboratorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    full_name: str
    org_name: str | None
    added_by: uuid.UUID
    created_at: datetime
