from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import BookingStatus

MAX_SEATS_PER_BOOKING = 10


class HoldCreate(BaseModel):
    # the upper bound limits how much of a hall one request can block
    seat_ids: list[int] = Field(min_length=1, max_length=MAX_SEATS_PER_BOOKING)


class HoldRead(BaseModel):
    """The hold token is the guest's only proof of ownership - there is no account."""

    hold_token: str
    seat_ids: list[int]
    expires_in: int = Field(description="seconds until the hold runs out")


class BookingCreate(BaseModel):
    hold_token: str = Field(min_length=1, max_length=100)
    guest_email: EmailStr


class BookingRead(BaseModel):
    reference: str
    showtime_id: int
    seat_ids: list[int]
    total_price: Decimal
    guest_email: EmailStr
    status: BookingStatus
