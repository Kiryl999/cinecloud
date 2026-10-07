from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional

from app.models.enums import BookingStatus

class Booking(SQLModel, table=True):
    __tablename__ = "bookings"
    # id alone is already unique; the pair exists as the target of the composite
    # foreign key from booking_seats, which pins each sold seat to the booking's
    # own showtime
    __table_args__ = (
        UniqueConstraint("id", "showtime_id", name="uq_booking_id_showtime"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    cinema_id: int = Field(foreign_key="cinemas.id")
    showtime_id: int = Field(foreign_key="showtimes.id")
    reference: str = Field(index=True, unique=True)
    guest_email: str = Field(index=True)
    status: BookingStatus = Field(default=BookingStatus.pending)
    total_price: Decimal = Field(max_digits=7, decimal_places=2)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    cinema: Optional["Cinema"] = Relationship(back_populates="bookings")
    showtime: Optional["Showtime"] = Relationship(back_populates="bookings")
