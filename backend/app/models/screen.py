from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional

class Screen(SQLModel, table=True):
    __tablename__ = "screens"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    capacity: int
    cinema_id: int = Field(foreign_key="cinemas.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    cinema: Optional["Cinema"] = Relationship(back_populates="screens")