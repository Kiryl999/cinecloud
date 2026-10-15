"""Tenant scoping for the public, token-less routes.

Admin routes take the tenant from the access token (see tenant_scope.py).
Visitor routes have no token, so the tenant comes from the cinema's slug in the
path instead, and a showtime is only found under the cinema it belongs to.
"""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.models.cinema import Cinema
from app.models.showtime import Showtime


async def get_cinema_or_404(db, slug: str) -> Cinema:
    result = await db.execute(select(Cinema).where(Cinema.slug == slug))
    cinema = result.scalar_one_or_none()
    if cinema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cinema not found")
    return cinema


def upcoming_showtimes(cinema_id: int):
    """Showtimes of one cinema that have not started yet, with movie and hall."""
    return (
        select(Showtime)
        .where(Showtime.cinema_id == cinema_id, Showtime.start_time > func.now())
        .options(selectinload(Showtime.movie), selectinload(Showtime.hall))
    )


async def get_upcoming_showtime_or_404(db, slug: str, showtime_id: int) -> Showtime:
    cinema = await get_cinema_or_404(db, slug)
    result = await db.execute(
        upcoming_showtimes(cinema.id).where(Showtime.id == showtime_id)
    )
    showtime = result.scalar_one_or_none()
    if showtime is None:
        # also for showtimes that have started and for those of other cinemas
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Showtime not found"
        )
    return showtime
