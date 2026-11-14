"""The bookings of the admin's cinema: who bought which seats.

Guests book without an account (see booking.py). This is the cinema's side of
the same records - to keep an eye on sales, or to look up a reference at the
door. Read-only: a sale is final.
"""

from collections import defaultdict
from typing import Annotated, Optional

from fastapi import APIRouter, Query
from sqlalchemy import or_
from sqlmodel import select

from app.api.deps import DbSession, TenantId
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.seat import Seat
from app.schemas.booking import BookedSeat, BookingOverview

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

MAX_LIMIT = 1000


@router.get("/", response_model=list[BookingOverview])
async def list_bookings(
    db: DbSession,
    tenant_id: TenantId,
    showtime_id: Optional[int] = None,
    q: Annotated[
        Optional[str],
        Query(max_length=254, description="A booking reference, or part of an e-mail address"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 100,
):
    """The newest bookings first.

    A showtime of another cinema finds nothing rather than a 404, the same as
    a showtime without bookings - see tenant_scope.py for why that matters.
    """
    query = select(Booking).where(Booking.cinema_id == tenant_id)
    if showtime_id is not None:
        query = query.where(Booking.showtime_id == showtime_id)
    if q and (term := q.strip()):
        query = query.where(
            or_(
                # references are upper case, but read out on the phone
                Booking.reference == term.upper(),
                Booking.guest_email.icontains(term, autoescape=True),
            )
        )
    bookings = (
        await db.execute(
            query.order_by(Booking.created_at.desc(), Booking.id.desc()).limit(limit)
        )
    ).scalars().all()

    seats = defaultdict(list)
    if bookings:
        rows = await db.execute(
            select(BookingSeat.booking_id, Seat.id, Seat.row_number, Seat.seat_number)
            .join(Seat, Seat.id == BookingSeat.seat_id)
            .where(BookingSeat.booking_id.in_([booking.id for booking in bookings]))
            .order_by(Seat.row_number, Seat.seat_number)
        )
        for row in rows:
            seats[row.booking_id].append(
                BookedSeat(id=row.id, row_number=row.row_number, seat_number=row.seat_number)
            )

    return [
        BookingOverview(
            reference=booking.reference,
            showtime_id=booking.showtime_id,
            guest_email=booking.guest_email,
            status=booking.status,
            total_price=booking.total_price,
            created_at=booking.created_at,
            seats=seats[booking.id],
        )
        for booking in bookings
    ]
