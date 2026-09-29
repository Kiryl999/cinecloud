from fastapi import APIRouter, HTTPException, status
from sqlalchemy import exists
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.deps import DbSession, TenantId
from app.api.scheduling import lock_schedule
from app.api.tenant_scope import get_owned_or_404
from app.models.hall import Hall
from app.models.seat import Seat
from app.models.showtime import Showtime
from app.schemas.hall import HallCreate, HallDetail, HallRead, HallUpdate

router = APIRouter(prefix="/halls", tags=["halls"])


def _as_detail(hall: Hall) -> dict:
    """Build the response payload; seats must already be eagerly loaded."""
    seats = sorted(hall.seats, key=lambda s: (s.row_number, s.seat_number))
    return {
        "id": hall.id,
        "cinema_id": hall.cinema_id,
        "name": hall.name,
        "seat_count": len(seats),
        "seats": seats,
    }


async def _load_with_seats(db, hall_id: int, tenant_id: int) -> Hall:
    result = await db.execute(
        select(Hall)
        .where(Hall.id == hall_id, Hall.cinema_id == tenant_id)
        .options(selectinload(Hall.seats))
    )
    return result.scalar_one()


@router.post("/", response_model=HallDetail, status_code=status.HTTP_201_CREATED)
async def create_hall(payload: HallCreate, db: DbSession, tenant_id: TenantId):
    hall = Hall(name=payload.name, cinema_id=tenant_id)
    db.add(hall)
    await db.flush()  # assigns hall.id without committing yet

    db.add_all(
        [
            Seat(hall_id=hall.id, row_number=row, seat_number=number)
            for row in range(1, payload.rows + 1)
            for number in range(1, payload.seats_per_row + 1)
        ]
    )
    await db.commit()

    return _as_detail(await _load_with_seats(db, hall.id, tenant_id))


@router.get("/", response_model=list[HallRead])
async def list_halls(db: DbSession, tenant_id: TenantId):
    result = await db.execute(
        select(Hall)
        .where(Hall.cinema_id == tenant_id)
        .options(selectinload(Hall.seats))
        .order_by(Hall.id)
    )
    return [_as_detail(hall) for hall in result.scalars().all()]


@router.get("/{hall_id}", response_model=HallDetail)
async def get_hall(hall_id: int, db: DbSession, tenant_id: TenantId):
    await get_owned_or_404(db, Hall, hall_id, tenant_id, name="Hall")
    return _as_detail(await _load_with_seats(db, hall_id, tenant_id))


@router.patch("/{hall_id}", response_model=HallDetail)
async def update_hall(hall_id: int, payload: HallUpdate, db: DbSession, tenant_id: TenantId):
    hall = await get_owned_or_404(db, Hall, hall_id, tenant_id, name="Hall")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hall, field, value)
    db.add(hall)
    await db.commit()

    return _as_detail(await _load_with_seats(db, hall_id, tenant_id))


@router.delete("/{hall_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hall(hall_id: int, db: DbSession, tenant_id: TenantId):
    await lock_schedule(db, tenant_id)
    await get_owned_or_404(db, Hall, hall_id, tenant_id, name="Hall")

    # same reasoning as for movies: the delete would null the hall and seat
    # references of every dependent showtime and fail with a 500
    if await db.scalar(select(exists().where(Showtime.hall_id == hall_id))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hall still has showtimes",
        )

    hall = await _load_with_seats(db, hall_id, tenant_id)
    for seat in hall.seats:
        await db.delete(seat)
    await db.delete(hall)
    await db.commit()
