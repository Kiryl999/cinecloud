"""Test fixtures.

The suite runs against a real PostgreSQL database, not SQLite: the application
uses asyncpg and Postgres-specific behaviour (timezone-aware timestamps, the
unique constraints guarding against double-booked seats), and a SQLite stand-in
would let tests pass that production would fail.

The database name is derived from the configured DATABASE_URL with a `_test`
suffix, so no credentials are duplicated into the repository.

Event loops matter here. asyncpg binds a connection to the loop that opened it,
and on Windows a connection outliving its loop dies with WinError 64. Every
fixture below is therefore function-scoped, and the one-off database setup runs
inside its own throw-away loop.
"""

import asyncio
import secrets
from dataclasses import dataclass
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.models  # noqa: F401  -- registers every model with the mapper
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models.booking import Booking
from app.models.booking_seat import BookingSeat
from app.models.cinema import Cinema
from app.models.cinema_admin import CinemaAdmin
from app.models.enums import BookingStatus

TEST_PASSWORD = "test-password-123"


def _test_url() -> str:
    """DATABASE_URL with a `_test` database name.

    `str(URL)` masks the password as `***`, which would silently produce a
    connection that Postgres rejects - so render it explicitly.
    """
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(
        hide_password=False
    )


async def _ensure_test_database(url: str) -> None:
    """Create the test database if it does not exist yet."""
    parsed = make_url(url)
    admin_dsn = make_url(url).set(
        drivername="postgresql", database="postgres"
    ).render_as_string(hide_password=False)
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval(
            "select 1 from pg_database where datname = $1", parsed.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await conn.close()


async def _reset_schema(url: str) -> None:
    """Start every run from exactly the tables the models describe today.

    The whole schema is dropped instead of calling metadata.drop_all, which only
    knows today's tables: one removed from the models would linger in the test
    database and block dropping every table it still references.
    """
    # destructive, so refuse anything that is not unmistakably a test database
    if not make_url(url).database.endswith("_test"):
        raise RuntimeError(f"refusing to reset non-test database {make_url(url).database!r}")

    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(SQLModel.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _test_url()
    asyncio.run(_ensure_test_database(url))
    asyncio.run(_reset_schema(url))
    return url


@pytest_asyncio.fixture
async def engine(database_url):
    eng = create_async_engine(database_url, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    """One session per test, followed by a full truncate.

    Truncating is slightly slower than rolling back a wrapping transaction, but
    it survives the commits the endpoints issue and keeps the fixtures readable.
    """
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s

    tables = ", ".join(f'"{t.name}"' for t in SQLModel.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client(session) -> AsyncClient:
    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def session_per_request(engine, client):
    """Give every request its own session and connection, as in production.

    `client` shares one session across all requests, which keeps the other
    fixtures simple - but two concurrent requests would then run inside one
    transaction and could never race each other. Tests about concurrency need
    the requests isolated the way real ones are.

    Takes `client` only to be set up after it: its override has to be in place
    before it can be swapped out here.
    """
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _own_session():
        async with maker() as s:
            yield s

    shared = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = _own_session
    yield
    app.dependency_overrides[get_db] = shared


@dataclass
class Tenant:
    """A cinema plus a logged-in admin belonging to it."""

    cinema_id: int
    admin_id: int
    email: str
    headers: dict


async def _make_tenant(session, client, slug: str) -> Tenant:
    cinema = Cinema(name=slug.replace("-", " ").title(), slug=slug)
    session.add(cinema)
    await session.flush()

    # a real-looking domain: `.example` and `.test` are reserved names that
    # Pydantic's EmailStr rejects, which would break the AdminRead response
    email = f"admin@{slug}.de"
    admin = CinemaAdmin(
        cinema_id=cinema.id,
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
    )
    session.add(admin)
    await session.commit()

    # go through the real login endpoint so the token is obtained exactly the
    # way a client would obtain it
    response = await client.post(
        "/auth/login", data={"username": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text

    return Tenant(
        cinema_id=cinema.id,
        admin_id=admin.id,
        email=email,
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )


@pytest_asyncio.fixture
async def tenant_a(session, client) -> Tenant:
    return await _make_tenant(session, client, "kino-alpha")


@pytest_asyncio.fixture
async def tenant_b(session, client) -> Tenant:
    return await _make_tenant(session, client, "kino-beta")


async def sell_seats(session, *, cinema_id: int, showtime_id: int, seat_ids) -> int:
    """Record a confirmed booking for `seat_ids` and return its id.

    Written straight to the database rather than through a booking flow: one
    bookings row plus one booking_seats row per seat, the shape a sale has.
    """
    booking = Booking(
        cinema_id=cinema_id,
        showtime_id=showtime_id,
        reference=secrets.token_hex(4),
        guest_email="guest@kino-alpha.de",
        status=BookingStatus.confirmed,
        total_price=Decimal("10.00") * len(seat_ids),
    )
    session.add(booking)
    await session.flush()  # assigns booking.id

    session.add_all(
        [
            BookingSeat(booking_id=booking.id, showtime_id=showtime_id, seat_id=seat_id)
            for seat_id in seat_ids
        ]
    )
    await session.commit()
    return booking.id
