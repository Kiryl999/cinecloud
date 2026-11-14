from fastapi import APIRouter, HTTPException, status
from sqlalchemy import exists, func
from sqlmodel import select

from app.api.deps import DbSession, TenantId
from app.api.scheduling import ensure_slot_is_free, lock_schedule
from app.api.tenant_scope import get_owned_or_404
from app.core.redis import RedisClient
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.hall import Hall
from app.models.movie import Movie
from app.models.showtime import Showtime
from app.schemas.public import SeatState
from app.schemas.showtime import (
    ShowtimeCreate,
    ShowtimeOverview,
    ShowtimeRead,
    ShowtimeUpdate,
)
from app.services import booking

router = APIRouter(prefix="/api/showtimes", tags=["showtimes"])


@router.post("/", response_model=ShowtimeRead, status_code=status.HTTP_201_CREATED)
async def create_showtime(payload: ShowtimeCreate, db: DbSession, tenant_id: TenantId):
    # taken before anything is read, so the checks below work on a schedule
    # that no concurrent request can change until this one commits
    await lock_schedule(db, tenant_id)

    # Both references are resolved through the tenant scope. Without this an
    # admin could schedule a showtime onto another cinema's movie or hall by
    # simply guessing an id - the foreign keys alone would happily accept it.
    movie = await get_owned_or_404(db, Movie, payload.movie_id, tenant_id, name="Movie")
    await get_owned_or_404(db, Hall, payload.hall_id, tenant_id, name="Hall")

    await ensure_slot_is_free(
        db,
        hall_id=payload.hall_id,
        start=payload.start_time,
        duration_minutes=movie.duration_minutes,
    )

    showtime = Showtime(**payload.model_dump(), cinema_id=tenant_id)
    db.add(showtime)
    await db.commit()
    await db.refresh(showtime)
    return showtime


@router.get("/", response_model=list[ShowtimeOverview])
async def list_showtimes(db: DbSession, tenant_id: TenantId):
    # counted per showtime inside the one query, through the unique index on
    # (showtime_id, seat_id) that guards against double-booking anyway
    seats_sold = (
        select(func.count())
        .select_from(BookingSeat)
        .where(BookingSeat.showtime_id == Showtime.id)
        .correlate(Showtime)
        .scalar_subquery()
    )
    result = await db.execute(
        select(Showtime, seats_sold)
        .where(Showtime.cinema_id == tenant_id)
        .order_by(Showtime.start_time)
    )
    return [
        ShowtimeOverview(
            **ShowtimeRead.model_validate(showtime).model_dump(), seats_sold=sold
        )
        for showtime, sold in result.all()
    ]


@router.get("/{showtime_id}", response_model=ShowtimeRead)
async def get_showtime(showtime_id: int, db: DbSession, tenant_id: TenantId):
    return await get_owned_or_404(
        db, Showtime, showtime_id, tenant_id, name="Showtime"
    )


@router.get("/{showtime_id}/seats", response_model=list[SeatState])
async def get_seat_map(
    showtime_id: int, db: DbSession, redis: RedisClient, tenant_id: TenantId
):
    """Every seat with its state: sold, held by a guest who is checking out,
    or free. Unlike the visitor's seat map, also for a showtime that has
    started."""
    showtime = await get_owned_or_404(
        db, Showtime, showtime_id, tenant_id, name="Showtime"
    )
    return await booking.seat_map(db, redis, showtime)


@router.patch("/{showtime_id}", response_model=ShowtimeRead)
async def update_showtime(
    showtime_id: int, payload: ShowtimeUpdate, db: DbSession, tenant_id: TenantId
):
    # hall_id is intentionally not updatable: seats already sold or held for
    # this showtime are seats of the current hall, and moving the showtime
    # would leave them pointing at a hall it no longer plays in.
    changes = payload.model_dump(exclude_unset=True)

    # a new start time or a movie with a different duration moves the slot
    reschedules = "movie_id" in changes or "start_time" in changes
    if reschedules:
        await lock_schedule(db, tenant_id)

    showtime = await get_owned_or_404(
        db, Showtime, showtime_id, tenant_id, name="Showtime"
    )

    if reschedules:
        movie = await get_owned_or_404(
            db, Movie, changes.get("movie_id", showtime.movie_id), tenant_id, name="Movie"
        )
        await ensure_slot_is_free(
            db,
            hall_id=showtime.hall_id,
            start=changes.get("start_time", showtime.start_time),
            duration_minutes=movie.duration_minutes,
            # its own current slot is not a clash
            ignore_showtime_id=showtime.id,
        )

    for field, value in changes.items():
        setattr(showtime, field, value)
    db.add(showtime)
    await db.commit()
    await db.refresh(showtime)
    return showtime


@router.delete("/{showtime_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_showtime(showtime_id: int, db: DbSession, tenant_id: TenantId):
    showtime = await get_owned_or_404(
        db, Showtime, showtime_id, tenant_id, name="Showtime"
    )

    # same reasoning as for movies and halls: SQLAlchemy would try to null the
    # showtime_id of every booking and fail on the NOT NULL column with a 500,
    # and deleting sold tickets along with the showtime is no option either
    if await db.scalar(select(exists().where(Booking.showtime_id == showtime_id))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Showtime already has bookings",
        )

    await db.delete(showtime)
    await db.commit()
