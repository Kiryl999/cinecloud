"""Central model registry.

SQLModel resolves relationships by class name at mapper configuration time,
so every model module has to be imported once before the first query runs.
Importing them here means `import app.models` is enough to register all of them.
"""

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.cinema import Cinema
from app.models.cinema_admin import CinemaAdmin
from app.models.enums import BookingStatus, SeatStatus
from app.models.hall import Hall
from app.models.movie import Movie
from app.models.seat import Seat
from app.models.showtime import Showtime

__all__ = [
    "Booking",
    "BookingSeat",
    "BookingStatus",
    "Cinema",
    "CinemaAdmin",
    "Hall",
    "Movie",
    "Seat",
    "SeatStatus",
    "Showtime",
]
