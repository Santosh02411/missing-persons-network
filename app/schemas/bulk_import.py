import uuid

from pydantic import BaseModel


class BulkImportRowError(BaseModel):
    row: int
    errors: list[str]


class BulkImportResult(BaseModel):
    created_count: int
    failed_count: int
    created_case_ids: list[uuid.UUID]
    errors: list[BulkImportRowError]
