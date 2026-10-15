from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import DbSession
from app.api.public_scope import (
    get_cinema_or_404,
    get_upcoming_showtime_or_404,
    upcoming_showtimes,
)
from app.core.redis import RedisClient
from app.models.cinema import Cinema
from app.models.showtime import Showtime
from app.schemas.cinema import CinemaRead
from app.schemas.public import PublicShowtime, PublicShowtimeDetail
from app.services import booking

# The visitor-facing side of the API: no token, the cinema comes from the slug
# in the path (see public_scope.py).
router = APIRouter(prefix="/cinemas", tags=["cinemas"])


@router.get("/", response_model=list[CinemaRead])
async def list_cinemas(db: DbSession):
    result = await db.execute(select(Cinema).order_by(Cinema.name))
    return result.scalars().all()


@router.get("/{slug}", response_model=CinemaRead)
async def get_cinema(slug: str, db: DbSession):
    return await get_cinema_or_404(db, slug)


@router.get("/{slug}/showtimes", response_model=list[PublicShowtime])
async def list_upcoming_showtimes(slug: str, db: DbSession):
    cinema = await get_cinema_or_404(db, slug)
    result = await db.execute(upcoming_showtimes(cinema.id).order_by(Showtime.start_time))
    return result.scalars().all()


@router.get("/{slug}/showtimes/{showtime_id}", response_model=PublicShowtimeDetail)
async def get_showtime_with_seats(
    slug: str, showtime_id: int, db: DbSession, redis: RedisClient
):
    showtime = await get_upcoming_showtime_or_404(db, slug, showtime_id)
    return {
        **PublicShowtime.model_validate(showtime).model_dump(),
        "seats": await booking.seat_map(db, redis, showtime),
    }
