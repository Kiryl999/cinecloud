from decimal import Decimal

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class Showtime(SQLModel, table=True):
    __tablename__ = "showtimes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    movie_id: int = Field(foreign_key="movies.id")
    hall_id: int = Field(foreign_key="halls.id")
    start_time: datetime = Field(index=True)
    ticket_price: Decimal = Field(max_digits=5, decimal_places=2) 
    
    movie: Optional["Movie"] = Relationship(back_populates="showtimes")
    hall: Optional["Hall"] = Relationship(back_populates="showtimes")
    
    bookings: List["Booking"] = Relationship(back_populates="showtime")
    showtime_seats: List["ShowtimeSeat"] = Relationship(back_populates="showtime")