from fastapi import APIRouter, HTTPException, status
from sqlalchemy import exists
from sqlmodel import select

from app.api.deps import DbSession, TenantId
from app.api.scheduling import ensure_slot_is_free, lock_schedule
from app.api.tenant_scope import get_owned_or_404
from app.models.movie import Movie
from app.models.showtime import Showtime
from app.schemas.movie import MovieCreate, MovieRead, MovieUpdate

router = APIRouter(prefix="/movies", tags=["movies"])


@router.post("/", response_model=MovieRead, status_code=status.HTTP_201_CREATED)
async def create_movie(payload: MovieCreate, db: DbSession, tenant_id: TenantId):
    movie = Movie(**payload.model_dump(), cinema_id=tenant_id)
    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    return movie


@router.get("/", response_model=list[MovieRead])
async def list_movies(db: DbSession, tenant_id: TenantId):
    result = await db.execute(
        select(Movie).where(Movie.cinema_id == tenant_id).order_by(Movie.id)
    )
    return result.scalars().all()


@router.get("/{movie_id}", response_model=MovieRead)
async def get_movie(movie_id: int, db: DbSession, tenant_id: TenantId):
    return await get_owned_or_404(db, Movie, movie_id, tenant_id, name="Movie")


@router.patch("/{movie_id}", response_model=MovieRead)
async def update_movie(
    movie_id: int, payload: MovieUpdate, db: DbSession, tenant_id: TenantId
):
    changes = payload.model_dump(exclude_unset=True)

    # a longer film can push its showtimes into the next one in the same hall
    if "duration_minutes" in changes:
        await lock_schedule(db, tenant_id)

    movie = await get_owned_or_404(db, Movie, movie_id, tenant_id, name="Movie")

    if "duration_minutes" in changes:
        showtimes = (
            await db.execute(select(Showtime).where(Showtime.movie_id == movie_id))
        ).scalars().all()
        # Other showtimes of this movie are still measured with the old duration
        # inside the query. An overlap between two of them is caught anyway:
        # it shows up when the earlier of the two is the one being checked.
        for showtime in showtimes:
            await ensure_slot_is_free(
                db,
                hall_id=showtime.hall_id,
                start=showtime.start_time,
                duration_minutes=changes["duration_minutes"],
                ignore_showtime_id=showtime.id,
            )

    for field, value in changes.items():
        setattr(movie, field, value)
    db.add(movie)
    await db.commit()
    await db.refresh(movie)
    return movie


@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(movie_id: int, db: DbSession, tenant_id: TenantId):
    await lock_schedule(db, tenant_id)
    movie = await get_owned_or_404(db, Movie, movie_id, tenant_id, name="Movie")

    # Without this check SQLAlchemy would set movie_id to NULL on every
    # dependent showtime and fail on the NOT NULL column with a 500. Deleting
    # the showtimes along with the movie is no option once bookings hang off them.
    if await db.scalar(select(exists().where(Showtime.movie_id == movie_id))):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie still has showtimes",
        )

    await db.delete(movie)
    await db.commit()
