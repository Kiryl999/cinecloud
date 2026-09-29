from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional

class Seat(SQLModel, table=True):
    __tablename__ = "seats"
    # a physical seat exists exactly once per hall
    __table_args__ = (
        UniqueConstraint("hall_id", "row_number", "seat_number", name="uq_seat_position"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    hall_id: int = Field(foreign_key="halls.id")
    row_number: int
    seat_number: int

    hall: Optional["Hall"] = Relationship(back_populates="seats")
    showtime_seats: List["ShowtimeSeat"] = Relationship(back_populates="seat")
