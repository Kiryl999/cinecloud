from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional

class CinemaAdmin(SQLModel, table=True):
    __tablename__ = "cinema_admins"

    id: Optional[int] = Field(default=None, primary_key=True)
    cinema_id: int = Field(foreign_key="cinemas.id")
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    cinema: Optional["Cinema"] = Relationship(back_populates="admins")
