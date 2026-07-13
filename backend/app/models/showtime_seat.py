from sqlmodel import SQLModel, Field, Relationship
from typing import Optional

class ShowtimeSeat(SQLModel, table=True):
    __tablename__ = "showtime_seats"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    showtime_id: int = Field(foreign_key="showtimes.id")
    seat_id: int = Field(foreign_key="seats.id")
    booking_id: Optional[int] = Field(foreign_key="bookings.id", default=None)
    is_available: bool = Field(default=True)
    
    showtime: Optional["Showtime"] = Relationship(back_populates="showtime_seats")
    seat: Optional["Seat"] = Relationship(back_populates="showtime_seats")
    booking: Optional["Booking"] = Relationship(back_populates="showtime_seats")