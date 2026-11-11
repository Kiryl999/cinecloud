"""Fill an existing cinema with a few days of demo programme.

The same programme a cinema can start with when it is opened in the app (see
app/services/demo.py) - for local development and load tests, or for a cinema
that was opened without it.

Usage:
    python -m scripts.seed_demo --slug cineplex-bonn
"""

import argparse
import asyncio

from sqlmodel import select

from app.core.database import SessionLocal
from app.models import Cinema, Movie
from app.services import demo


async def seed(slug: str, days: int) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(Cinema).where(Cinema.slug == slug))
        cinema = result.scalar_one_or_none()
        if cinema is None:
            raise SystemExit(f"No cinema with slug '{slug}'.")

        existing = await db.execute(select(Movie.id).where(Movie.cinema_id == cinema.id))
        if existing.first() is not None:
            raise SystemExit(f"'{cinema.name}' already has movies - not seeding twice.")

        added = await demo.fill(db, cinema.id, days)
        print(
            f"Seeded '{cinema.name}': {added.movies} movies, {added.halls} halls, "
            f"{added.showtimes} showtimes from {added.first_day} on."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill a cinema with demo programme.")
    parser.add_argument("--slug", required=True, help="slug of an existing cinema")
    parser.add_argument("--days", type=int, default=7, help="days of programme to create")
    args = parser.parse_args()

    asyncio.run(seed(args.slug, args.days))


if __name__ == "__main__":
    main()
