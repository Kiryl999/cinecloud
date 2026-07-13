from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

from app.models.enums import BookingStatus

class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    showtime_id: int = Field(foreign_key="showtimes.id")
    status: BookingStatus = Field(default=BookingStatus.pending)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # will using auth system for user_id, for now we can just use a string to represent the user
    user_id: str = Field(index=True)
    
    showtime: Optional["Showtime"] = Relationship(back_populates="bookings")
    showtime_seats: List["ShowtimeSeat"] = Relationship(back_populates="booking")