"""Response schemas for the public, unauthenticated visitor endpoints.

They carry only what a visitor needs to browse the programme and pick seats:
no tenant ids, no booking references, no hold deadlines.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import SeatStatus


class MovieSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    release_year: int
    duration_minutes: int
    poster_key: Optional[str]


class HallSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class PublicShowtime(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    ticket_price: Decimal
    movie: MovieSummary
    hall: HallSummary


class SeatState(BaseModel):
    """One seat of a showtime as a visitor sees it.

    `id` is the physical seat in the hall. Together with the showtime it is
    what a reservation and a sale refer to.
    """

    id: int
    row_number: int
    seat_number: int
    status: SeatStatus


class PublicShowtimeDetail(PublicShowtime):
    seats: List[SeatState]
