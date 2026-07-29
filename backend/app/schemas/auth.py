from pydantic import BaseModel, ConfigDict, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminRead(BaseModel):
    """Response schema for admins - deliberately excludes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    cinema_id: int
