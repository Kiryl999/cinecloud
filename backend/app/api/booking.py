"""Guest booking: live seat map, seat holds and bookings.

No token anywhere - guests have no account. Possession of the hold token
returned when reserving is what lets a guest book the held seats.
"""

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import DbSession
from app.api.public_scope import get_upcoming_showtime_or_404
from app.core import metrics
from app.core.database import get_session_factory
from app.core.redis import RedisClient
from app.models.showtime import Showtime
from app.schemas.booking import BookingCreate, BookingRead, HoldCreate, HoldRead
from app.services import booking, mail, seat_holds

router = APIRouter(prefix="/cinemas/{slug}/showtimes/{showtime_id}", tags=["booking"])

SessionFactory = Annotated[async_sessionmaker, Depends(get_session_factory)]

# A comment line every so often keeps proxies and load balancers from closing
# a stream that has been quiet for a while.
KEEPALIVE_SECONDS = 15


def _event(name: str, data: str) -> str:
    return f"event: {name}\ndata: {data}\n\n"


async def seat_events(
    redis: Redis,
    sessions: async_sessionmaker,
    showtime: Showtime,
    *,
    keepalive_seconds: float = KEEPALIVE_SECONDS,
):
    """Server-sent events for one showtime: a snapshot, then every change.

    The subscription is confirmed before the snapshot is read, so a change that
    happens in between is never lost - it is either in the snapshot already or
    arrives as an event afterwards. Redis Pub/Sub keeps no history, which is why
    every connection, including the browser's automatic reconnects, starts
    with a fresh snapshot.
    """
    pubsub = redis.pubsub()
    metrics.SEAT_STREAMS.inc()
    try:
        await pubsub.subscribe(seat_holds.channel(showtime.id))
        # the first message is Redis confirming the subscription
        await pubsub.get_message(timeout=5)

        async with sessions() as db:
            seats = await booking.seat_map(db, redis, showtime)
        yield _event(
            "snapshot", json.dumps({"seats": [s.model_dump(mode="json") for s in seats]})
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=keepalive_seconds
            )
            if message is None:
                yield ": keep-alive\n\n"
            else:
                # published as JSON already: {"event": "held" | "booked", ...}
                yield _event("seats", message["data"])
    finally:
        metrics.SEAT_STREAMS.dec()
        await pubsub.aclose()


@router.get("/seats/stream")
async def stream_seats(
    slug: str, showtime_id: int, db: DbSession, redis: RedisClient, sessions: SessionFactory
):
    showtime = await get_upcoming_showtime_or_404(db, slug, showtime_id)
    return StreamingResponse(
        seat_events(redis, sessions, showtime),
        media_type="text/event-stream",
        # browsers must not cache the stream, reverse proxies must not buffer it
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/holds", response_model=HoldRead, status_code=status.HTTP_201_CREATED)
async def reserve_seats(
    slug: str, showtime_id: int, payload: HoldCreate, db: DbSession, redis: RedisClient
):
    showtime = await get_upcoming_showtime_or_404(db, slug, showtime_id)
    try:
        hold = await booking.reserve(db, redis, showtime, payload.seat_ids)
    except booking.SeatsNotInHall:
        metrics.SEAT_HOLDS.labels("invalid").inc()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Seat is not part of this showtime's hall",
        )
    except booking.SeatsUnavailable:
        metrics.SEAT_HOLDS.labels("unavailable").inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seats already reserved or sold",
        )
    metrics.SEAT_HOLDS.labels("placed").inc()
    return HoldRead(hold_token=hold.token, seat_ids=hold.seat_ids, expires_in=hold.expires_in)


@router.post("/bookings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def book_seats(
    slug: str,
    showtime_id: int,
    payload: BookingCreate,
    background: BackgroundTasks,
    db: DbSession,
    redis: RedisClient,
):
    showtime = await get_upcoming_showtime_or_404(db, slug, showtime_id)
    try:
        sale = await booking.book(db, redis, showtime, payload.hold_token, payload.guest_email)
    except booking.HoldExpired:
        metrics.BOOKINGS.labels("expired").inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Reservation expired"
        )
    except booking.SeatsUnavailable:
        metrics.BOOKINGS.labels("unavailable").inc()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Seats already sold"
        )
    metrics.BOOKINGS.labels("confirmed").inc()
    metrics.SEATS_SOLD.inc(len(sale.seat_ids))

    # after the response: the guest should not wait for mail delivery
    background.add_task(
        mail.send_booking_confirmation,
        to=sale.booking.guest_email,
        reference=sale.booking.reference,
        seat_count=len(sale.seat_ids),
    )
    return BookingRead(
        reference=sale.booking.reference,
        showtime_id=showtime.id,
        seat_ids=sale.seat_ids,
        total_price=sale.booking.total_price,
        guest_email=sale.booking.guest_email,
        status=sale.booking.status,
    )
