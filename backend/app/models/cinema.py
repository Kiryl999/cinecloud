from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Cinema(SQLModel, table=True):
    __tablename__ = "cinemas"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    admins: List["CinemaAdmin"] = Relationship(back_populates="cinema")
    movies: List["Movie"] = Relationship(back_populates="cinema")
    halls: List["Hall"] = Relationship(back_populates="cinema")
    showtimes: List["Showtime"] = Relationship(back_populates="cinema")
    bookings: List["Booking"] = Relationship(back_populates="cinema")
