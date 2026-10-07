from decimal import Decimal

from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class Showtime(SQLModel, table=True):
    __tablename__ = "showtimes"

    id: Optional[int] = Field(default=None, primary_key=True)
    cinema_id: int = Field(foreign_key="cinemas.id")
    movie_id: int = Field(foreign_key="movies.id")
    hall_id: int = Field(foreign_key="halls.id")
    start_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    ticket_price: Decimal = Field(max_digits=5, decimal_places=2)

    cinema: Optional["Cinema"] = Relationship(back_populates="showtimes")
    movie: Optional["Movie"] = Relationship(back_populates="showtimes")
    hall: Optional["Hall"] = Relationship(back_populates="showtimes")

    bookings: List["Booking"] = Relationship(back_populates="showtime")
