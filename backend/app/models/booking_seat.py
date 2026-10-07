from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel


class BookingSeat(SQLModel, table=True):
    """One seat sold within one booking.

    A row exists exactly when the seat is sold for that showtime; free seats have
    no row at all. The unique constraint is the database's own guarantee against
    double-booking: whatever happens before it - holds, application checks - a
    seat can be sold only once per showtime.

    showtime_id repeats bookings.showtime_id so that the constraint can cover it.
    The composite foreign key keeps the two copies from drifting apart.
    """

    __tablename__ = "booking_seats"
    __table_args__ = (
        UniqueConstraint("showtime_id", "seat_id", name="uq_booking_seat_per_showtime"),
        ForeignKeyConstraint(
            ["booking_id", "showtime_id"],
            ["bookings.id", "bookings.showtime_id"],
            name="fk_booking_seats_booking",
        ),
    )

    booking_id: int = Field(primary_key=True)
    seat_id: int = Field(foreign_key="seats.id", primary_key=True)
    showtime_id: int = Field(foreign_key="showtimes.id")
