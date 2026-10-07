from fastapi import APIRouter, HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.deps import DbSession
from app.models.booking_seat import BookingSeat
from app.models.cinema import Cinema
from app.models.enums import SeatStatus
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.schemas.cinema import CinemaRead
from app.schemas.public import PublicShowtime, PublicShowtimeDetail

# The visitor-facing side of the API. Nothing here requires a token, so the
# tenant cannot come from one: every route is scoped by the cinema's slug in the
# path instead, and a showtime is only found under the cinema it belongs to.
router = APIRouter(prefix="/cinemas", tags=["cinemas"])


async def _cinema_or_404(db, slug: str) -> Cinema:
    result = await db.execute(select(Cinema).where(Cinema.slug == slug))
    cinema = result.scalar_one_or_none()
    if cinema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cinema not found")
    return cinema


def _upcoming_showtimes(cinema_id: int):
    """Showtimes of one cinema that have not started yet, with movie and hall."""
    return (
        select(Showtime)
        .where(Showtime.cinema_id == cinema_id, Showtime.start_time > func.now())
        .options(selectinload(Showtime.movie), selectinload(Showtime.hall))
    )


@router.get("/", response_model=list[CinemaRead])
async def list_cinemas(db: DbSession):
    result = await db.execute(select(Cinema).order_by(Cinema.name))
    return result.scalars().all()


@router.get("/{slug}", response_model=CinemaRead)
async def get_cinema(slug: str, db: DbSession):
    return await _cinema_or_404(db, slug)


@router.get("/{slug}/showtimes", response_model=list[PublicShowtime])
async def list_upcoming_showtimes(slug: str, db: DbSession):
    cinema = await _cinema_or_404(db, slug)
    result = await db.execute(
        _upcoming_showtimes(cinema.id).order_by(Showtime.start_time)
    )
    return result.scalars().all()


@router.get("/{slug}/showtimes/{showtime_id}", response_model=PublicShowtimeDetail)
async def get_showtime_with_seats(slug: str, showtime_id: int, db: DbSession):
    cinema = await _cinema_or_404(db, slug)
    result = await db.execute(
        _upcoming_showtimes(cinema.id).where(Showtime.id == showtime_id)
    )
    showtime = result.scalar_one_or_none()
    if showtime is None:
        # also for showtimes that have started and for those of other cinemas
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Showtime not found"
        )

    # Free seats have no row in booking_seats: every seat of the hall is listed,
    # and the sold ones are found by an outer join restricted to this showtime.
    sold = BookingSeat.seat_id.is_not(None)
    seats = await db.execute(
        select(
            Seat.id,
            Seat.row_number,
            Seat.seat_number,
            case(
                (sold, SeatStatus.booked.value), else_=SeatStatus.available.value
            ).label("status"),
        )
        .outerjoin(
            BookingSeat,
            (BookingSeat.seat_id == Seat.id) & (BookingSeat.showtime_id == showtime.id),
        )
        .where(Seat.hall_id == showtime.hall_id)
        .order_by(Seat.row_number, Seat.seat_number)
    )

    return {
        **PublicShowtime.model_validate(showtime).model_dump(),
        "seats": [dict(seat._mapping) for seat in seats],
    }
