"""A week of demo programme for a cinema.

Offered when a cinema is opened, and used by scripts/seed_demo.py for local
development and load tests: without it the visitor pages have nothing to show
until someone schedules showtimes by hand.

Everything goes through the same functions the API uses, so the demo data obeys
the same rules: halls get their seat grid, and showtimes in one hall never
overlap.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.halls import create_hall
from app.api.movies import create_movie
from app.api.showtimes import create_showtime
from app.schemas.hall import HallCreate
from app.schemas.movie import MovieCreate
from app.schemas.showtime import ShowtimeCreate

MOVIES = [
    MovieCreate(
        title="Dune: Part Two",
        description="Paul Atreides unites with the Fremen on a path of revenge.",
        release_year=2024,
        duration_minutes=166,
    ),
    MovieCreate(
        title="Arrival",
        description="A linguist is recruited to talk to visitors from space.",
        release_year=2016,
        duration_minutes=116,
    ),
    MovieCreate(
        title="Past Lives",
        description="Two childhood friends meet again after twenty years.",
        release_year=2023,
        duration_minutes=106,
    ),
]

HALLS = [
    HallCreate(name="Saal 1", rows=8, seats_per_row=12),
    HallCreate(name="Saal 2", rows=6, seats_per_row=10),
]

# (hall, movie, start in UTC, price), repeated every day. Visitors see the times
# in Berlin time - 17:00, 20:30, 18:00 and 21:00 in summer. Spaced so that no two
# showtimes in one hall overlap, turnaround included.
DAILY_PLAN = [
    (0, 0, time(15, 0), "12.50"),
    (0, 1, time(18, 30), "11.00"),
    (1, 2, time(16, 0), "10.00"),
    (1, 1, time(19, 0), "11.00"),
]


@dataclass
class DemoProgramme:
    movies: int
    halls: int
    showtimes: int
    first_day: date


async def fill(db: AsyncSession, cinema_id: int, days: int = 7) -> DemoProgramme:
    """Add the demo movies and halls, and showtimes from tomorrow on."""
    movies = [await create_movie(movie, db, cinema_id) for movie in MOVIES]
    halls = [await create_hall(hall, db, cinema_id) for hall in HALLS]

    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    showtimes = 0
    for offset in range(days):
        day = tomorrow + timedelta(days=offset)
        for hall_index, movie_index, start, price in DAILY_PLAN:
            await create_showtime(
                ShowtimeCreate(
                    movie_id=movies[movie_index].id,
                    hall_id=halls[hall_index]["id"],
                    start_time=datetime.combine(day, start, tzinfo=timezone.utc),
                    ticket_price=Decimal(price),
                ),
                db,
                cinema_id,
            )
            showtimes += 1

    return DemoProgramme(len(movies), len(halls), showtimes, tomorrow)
