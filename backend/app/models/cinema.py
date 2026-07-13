from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Cinema(SQLModel, table=True):
    __tablename__ = "cinemas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))    
    
    movies: List["Movie"] = Relationship(back_populates="cinema")
    halls: List["Hall"] = Relationship(back_populates="cinema")