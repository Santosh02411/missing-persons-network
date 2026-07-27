from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  # user id, as string
    exp: int
    type: str  # "access" | "refresh"


class RefreshRequest(BaseModel):
    refresh_token: str
