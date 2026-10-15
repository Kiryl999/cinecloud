"""Reserving and booking seats as a guest.

Two stores, two roles: Redis holds seats while a guest checks out, PostgreSQL
records what is sold. When a booking is confirmed, PostgreSQL decides first -
Redis is cleaned up and the change announced only after the sale is committed,
so nobody is ever told about a sale that did not happen.
"""

import logging
import secrets
from dataclasses import dataclass
from decimal import Decimal

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.enums import BookingStatus, SeatStatus
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.schemas.public import SeatState
from app.services import seat_holds

logger = logging.getLogger("cinecloud.booking")

# no 0/O or 1/I: references get read out on the phone and typed off a screen
_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class SeatsNotInHall(Exception):
    """A requested seat does not belong to the showtime's hall."""


class SeatsUnavailable(Exception):
    """A requested seat is held by someone else or already sold."""


class HoldExpired(Exception):
    """The hold behind a booking request has expired or is not this guest's."""


@dataclass
class Sale:
    booking: Booking
    seat_ids: list[int]


async def seat_map(db: AsyncSession, redis: Redis, showtime: Showtime) -> list[SeatState]:
    """Every seat of the showtime's hall with its current state.

    Sold seats come from PostgreSQL, held ones from Redis - and sold wins. A
    hold key can outlive its sale, for instance when Redis was unreachable right
    after the commit; the seat must still read as sold.
    """
    sold = BookingSeat.seat_id.is_not(None)
    rows = (
        await db.execute(
            select(Seat.id, Seat.row_number, Seat.seat_number, sold.label("sold"))
            .outerjoin(
                BookingSeat,
                (BookingSeat.seat_id == Seat.id) & (BookingSeat.showtime_id == showtime.id),
            )
            .where(Seat.hall_id == showtime.hall_id)
            .order_by(Seat.row_number, Seat.seat_number)
        )
    ).all()

    try:
        held = await seat_holds.seconds_left(
            redis, showtime.id, [row.id for row in rows if not row.sold]
        )
    except RedisError:
        # Degrade instead of failing: the map stays usable without holds, and
        # reserving still fails safely because it cannot work without Redis.
        logger.warning("Redis unreachable - seat map of showtime %s shows no holds", showtime.id)
        held = {}

    def state(row) -> SeatState:
        if row.sold:
            return SeatState(id=row.id, row_number=row.row_number,
                             seat_number=row.seat_number, status=SeatStatus.booked)
        if row.id in held:
            return SeatState(id=row.id, row_number=row.row_number,
                             seat_number=row.seat_number, status=SeatStatus.held,
                             hold_expires_in=held[row.id])
        return SeatState(id=row.id, row_number=row.row_number,
                         seat_number=row.seat_number, status=SeatStatus.available)

    return [state(row) for row in rows]


async def reserve(
    db: AsyncSession, redis: Redis, showtime: Showtime, seat_ids: list[int]
) -> seat_holds.Hold:
    """Hold seats for one guest. All of them or none."""
    seat_ids = sorted(set(seat_ids))

    in_hall = await db.scalar(
        select(func.count())
        .select_from(Seat)
        .where(Seat.id.in_(seat_ids), Seat.hall_id == showtime.hall_id)
    )
    if in_hall != len(seat_ids):
        raise SeatsNotInHall()

    # Redis knows nothing about sales, so ask the record of them first. A sale
    # committed right after this check is still caught when booking.
    already_sold = await db.scalar(
        select(func.count())
        .select_from(BookingSeat)
        .where(BookingSeat.showtime_id == showtime.id, BookingSeat.seat_id.in_(seat_ids))
    )
    if already_sold:
        raise SeatsUnavailable()

    hold = await seat_holds.place(redis, showtime.id, seat_ids)
    if hold is None:
        raise SeatsUnavailable()
    return hold


async def book(
    db: AsyncSession, redis: Redis, showtime: Showtime, hold_token: str, guest_email: str
) -> Sale:
    """Turn a hold into a sale."""
    seat_ids = await seat_holds.secure(redis, showtime.id, hold_token)
    if seat_ids is None:
        raise HoldExpired()

    total = showtime.ticket_price * len(seat_ids)
    _simulate_payment(total)

    booking = Booking(
        cinema_id=showtime.cinema_id,
        showtime_id=showtime.id,
        reference=_new_reference(),
        guest_email=guest_email,
        status=BookingStatus.confirmed,
        total_price=total,
    )
    db.add(booking)
    try:
        await db.flush()  # assigns booking.id
        db.add_all(
            [
                BookingSeat(booking_id=booking.id, showtime_id=showtime.id, seat_id=seat_id)
                for seat_id in seat_ids
            ]
        )
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        # The last line of defence: a hold that got past every earlier check,
        # for instance one that Redis lost in a failover. Nothing to undo in
        # Redis - it has not been touched yet.
        if "uq_booking_seat_per_showtime" in str(error.orig):
            raise SeatsUnavailable() from error
        raise

    try:
        await seat_holds.release(redis, showtime.id, hold_token, seat_ids)
    except RedisError:
        # The sale is committed and stands. The hold runs out by itself, and
        # until then the seat map prefers the sold state anyway.
        logger.warning("could not release the hold of booking %s", booking.reference)

    return Sale(booking, seat_ids)


def _simulate_payment(amount: Decimal) -> None:
    """Stand-in for a payment provider: approves every amount.

    A real provider would be called here, between securing the hold and
    recording the sale. The hold's confirm window covers that round trip.
    """


def _new_reference() -> str:
    # random rather than sequential, so references cannot be enumerated
    return "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(8))
