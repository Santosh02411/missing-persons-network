from pydantic import BaseModel


class WatchStatus(BaseModel):
    is_watching: bool
