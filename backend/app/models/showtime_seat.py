from datetime import datetime
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Column, String, Field, Relationship
from typing import Optional

from app.models.enums import SeatStatus

class ShowtimeSeat(SQLModel, table=True):
    __tablename__ = "showtime_seats"

    id: Optional[int] = Field(default=None, primary_key=True)
    showtime_id: int = Field(foreign_key="showtimes.id")
    seat_id: int = Field(foreign_key="seats.id")
    booking_id: Optional[int] = Field(foreign_key="bookings.id", default=None)
    status: SeatStatus = Field(
        default=SeatStatus.available,
        sa_column=Column(String, nullable=False, server_default="available")
    )
    held_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    showtime: Optional["Showtime"] = Relationship(back_populates="showtime_seats")
    seat: Optional["Seat"] = Relationship(back_populates="showtime_seats")
    booking: Optional["Booking"] = Relationship(back_populates="showtime_seats")
