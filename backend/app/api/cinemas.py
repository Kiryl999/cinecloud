from fastapi import APIRouter, HTTPException, status
from sqlalchemy import exists
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.deps import CurrentSubject, DbSession
from app.api.public_scope import (
    get_cinema_or_404,
    get_upcoming_showtime_or_404,
    upcoming_showtimes,
)
from app.core.redis import RedisClient
from app.models.cinema import Cinema
from app.models.cinema_admin import CinemaAdmin
from app.models.showtime import Showtime
from app.schemas.cinema import CinemaCreate, CinemaRead
from app.schemas.public import PublicShowtime, PublicShowtimeDetail
from app.services import booking, demo

# The visitor-facing side of the API: no token, the cinema comes from the slug
# in the path (see public_scope.py). Opening a cinema is the one exception.
router = APIRouter(prefix="/api/cinemas", tags=["cinemas"])


@router.post("/", response_model=CinemaRead, status_code=status.HTTP_201_CREATED)
async def open_cinema(payload: CinemaCreate, db: DbSession, subject: CurrentSubject):
    """Self-service sign-up: an account that manages no cinema yet opens one
    and becomes its first admin."""
    # an account manages exactly one cinema
    if await db.scalar(select(exists().where(CinemaAdmin.subject == subject))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already manages a cinema",
        )
    if await db.scalar(select(exists().where(Cinema.slug == payload.slug))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The address {payload.slug} is taken by another cinema",
        )

    cinema = Cinema(name=payload.name, slug=payload.slug)
    db.add(cinema)
    try:
        await db.flush()  # assigns cinema.id
        db.add(CinemaAdmin(cinema_id=cinema.id, subject=subject))
        await db.commit()
    except IntegrityError:
        # A concurrent request took the address or opened a cinema for this
        # account after the checks above. The unique constraints keep both
        # rules all the same; this only puts the refusal into words.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The address or this account was taken just now - please try again",
        )

    if payload.demo_programme:
        await demo.fill(db, cinema.id)
    return cinema


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
