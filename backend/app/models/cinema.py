from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Cinema(SQLModel, table=True):
    __tablename__ = "cinemas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    screens: List["Screen"] = Relationship(back_populates="cinema")