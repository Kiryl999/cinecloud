from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Movie(SQLModel, table=True):
    __tablename__ = "movies"

    id: Optional[int] = Field(default=None, primary_key=True)
    cinema_id: int = Field(foreign_key="cinemas.id")
    title: str
    description: str
    release_year: int
    duration_minutes: int
    poster_key: Optional[str] = Field(default=None)

    showtimes: List["Showtime"] = Relationship(back_populates="movie")
    cinema: Optional["Cinema"] = Relationship(back_populates="movies")
