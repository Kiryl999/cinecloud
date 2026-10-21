"""Liveness and readiness probes.

The point of having two is what each one ignores: liveness must stay green
while PostgreSQL is down, readiness must not depend on Redis.
"""

import asyncio

from redis.asyncio import Redis

from app.api import health
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import app


class _BrokenSession:
    """Stands in for a session whose database cannot be reached."""

    async def execute(self, *_args, **_kwargs):
        raise ConnectionRefusedError("database unreachable")


class _HangingSession:
    """Stands in for a database that accepts the connection but never answers."""

    async def execute(self, *_args, **_kwargs):
        await asyncio.sleep(10)


def _use_session(fake) -> None:
    async def _override():
        yield fake

    app.dependency_overrides[get_db] = _override


async def test_ready_when_the_database_answers(client):
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_not_ready_without_the_database(client):
    _use_session(_BrokenSession())

    response = await client.get("/health/ready")

    assert response.status_code == 503


async def test_not_ready_when_the_database_hangs(client, monkeypatch):
    monkeypatch.setattr(health, "READINESS_TIMEOUT_SECONDS", 0.1)
    _use_session(_HangingSession())

    response = await client.get("/health/ready")

    assert response.status_code == 503


async def test_still_alive_without_the_database(client):
    """A restart would not bring the database back - liveness must not ask it."""
    _use_session(_BrokenSession())

    response = await client.get("/health/live")

    assert response.status_code == 200


async def test_still_ready_without_redis(client):
    unreachable = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    app.dependency_overrides[get_redis] = lambda: unreachable
    try:
        response = await client.get("/health/ready")
    finally:
        await unreachable.aclose()

    assert response.status_code == 200
