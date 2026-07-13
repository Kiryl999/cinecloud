from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional

class Hall(SQLModel, table=True):
    __tablename__ = "halls"
    
    id: Optional[int] = Field(default=None, primary_key=True) 
    name: str = Field(index=True)
    cinema_id: int = Field(foreign_key="cinemas.id")
    
    showtimes: List["Showtime"] = Relationship(back_populates="hall")
    seats: List["Seat"] = Relationship(back_populates="hall")
    cinema: Optional["Cinema"] = Relationship(back_populates="halls")
    
    
