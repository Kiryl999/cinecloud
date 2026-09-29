"""Scheduling rules shared by the movie, hall and showtime routers.

A hall shows one film at a time, followed by a turnaround for cleaning and
admission. A showtime's end is not stored - it follows from the movie's
duration - so the rule is enforced here rather than by a database constraint,
and has to be re-checked whenever a start time or a duration changes.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import Interval, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cinema import Cinema
from app.models.movie import Movie
from app.models.showtime import Showtime

# time a hall needs between two showtimes for cleaning and admission
TURNAROUND_MINUTES = 15

_ONE_MINUTE = literal_column("interval '1 minute'", type_=Interval)


async def lock_schedule(db: AsyncSession, cinema_id: int) -> None:
    """Serialise schedule changes within one cinema until the transaction ends.

    "Check the slot is free, then insert" is a check-then-act sequence: two
    concurrent requests could both find the slot free and both insert. Locking
    the cinema row makes the second request wait until the first has committed,
    so its check then sees the new showtime.

    FOR NO KEY UPDATE rather than FOR UPDATE: it still excludes concurrent
    schedule changes, but does not block inserts that merely reference the
    cinema through a foreign key, such as bookings.
    """
    await db.execute(
        select(Cinema.id)
        .where(Cinema.id == cinema_id)
        .with_for_update(key_share=True)
    )


async def ensure_slot_is_free(
    db: AsyncSession,
    *,
    hall_id: int,
    start: datetime,
    duration_minutes: int,
    ignore_showtime_id: Optional[int] = None,
) -> None:
    """Raise 409 if the slot overlaps another showtime in the same hall.

    Each showtime occupies [start, start + duration + turnaround). Two such
    intervals overlap exactly when each one starts before the other one ends.
    """
    end = start + timedelta(minutes=duration_minutes + TURNAROUND_MINUTES)
    existing_end = Showtime.start_time + _ONE_MINUTE * (
        Movie.duration_minutes + TURNAROUND_MINUTES
    )

    query = (
        select(Showtime.id, Showtime.start_time)
        .join(Movie, Movie.id == Showtime.movie_id)
        .where(
            Showtime.hall_id == hall_id,
            Showtime.start_time < end,
            existing_end > start,
        )
        .order_by(Showtime.start_time)
        .limit(1)
    )
    if ignore_showtime_id is not None:
        query = query.where(Showtime.id != ignore_showtime_id)

    clash = (await db.execute(query)).first()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Hall is already in use by showtime {clash.id} "
                f"starting at {clash.start_time.isoformat()}"
            ),
        )
