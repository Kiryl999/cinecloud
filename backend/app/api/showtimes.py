from fastapi import APIRouter, status
from sqlmodel import select

from app.api.deps import DbSession, TenantId
from app.api.scheduling import ensure_slot_is_free, lock_schedule
from app.api.tenant_scope import get_owned_or_404
from app.models.hall import Hall
from app.models.movie import Movie
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.models.showtime_seat import ShowtimeSeat
from app.schemas.showtime import ShowtimeCreate, ShowtimeRead, ShowtimeUpdate

router = APIRouter(prefix="/showtimes", tags=["showtimes"])


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
    await db.flush()  # assigns showtime.id without committing yet

    # materialise one seat instance per hall seat - this is the Saalplan that
    # the booking flow will later hold and book against
    seat_ids = (
        await db.execute(select(Seat.id).where(Seat.hall_id == payload.hall_id))
    ).scalars().all()
    db.add_all(
        [ShowtimeSeat(showtime_id=showtime.id, seat_id=seat_id) for seat_id in seat_ids]
    )

    await db.commit()
    await db.refresh(showtime)
    return showtime


@router.get("/", response_model=list[ShowtimeRead])
async def list_showtimes(db: DbSession, tenant_id: TenantId):
    result = await db.execute(
        select(Showtime)
        .where(Showtime.cinema_id == tenant_id)
        .order_by(Showtime.start_time)
    )
    return result.scalars().all()


@router.get("/{showtime_id}", response_model=ShowtimeRead)
async def get_showtime(showtime_id: int, db: DbSession, tenant_id: TenantId):
    return await get_owned_or_404(
        db, Showtime, showtime_id, tenant_id, name="Showtime"
    )


@router.patch("/{showtime_id}", response_model=ShowtimeRead)
async def update_showtime(
    showtime_id: int, payload: ShowtimeUpdate, db: DbSession, tenant_id: TenantId
):
    # hall_id is intentionally not updatable: the showtime_seats are already
    # materialised against the current hall, and moving the showtime would
    # orphan them together with any holds or bookings attached.
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
    seats = (
        await db.execute(
            select(ShowtimeSeat).where(ShowtimeSeat.showtime_id == showtime_id)
        )
    ).scalars().all()
    for seat in seats:
        await db.delete(seat)
    await db.delete(showtime)
    await db.commit()
