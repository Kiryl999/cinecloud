"""Prometheus metrics.

Counters are process-wide and keep counting across tests, so every assertion
compares a value before and after the action instead of an absolute number.
"""

import asyncio

from prometheus_client import REGISTRY
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.booking import seat_events
from app.core.redis import get_redis
from app.main import app
from app.models.showtime import Showtime
from tests.test_booking import _showtime


def _value(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _requests(handler: str, status: str, method: str = "GET") -> float:
    return _value("http_requests_total", handler=handler, method=method, status=status)


# --- the endpoint and HTTP metrics --------------------------------------------


async def test_metrics_are_served_in_prometheus_format(internal_client):
    response = await internal_client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in response.text
    assert 'cinecloud_seat_holds_total{outcome="placed"}' in response.text


async def test_requests_are_counted_by_route_template_and_exact_status(client):
    """One series per route rather than per URL, and 404 kept apart from 409."""
    before = _requests("/api/cinemas/{slug}", "404")

    await client.get("/cinemas/no-such-cinema")

    assert _requests("/api/cinemas/{slug}", "404") == before + 1


async def test_probes_and_scrapes_are_not_counted(internal_client):
    await internal_client.get("/health/live")
    await internal_client.get("/metrics")

    assert _requests("/health/live", "200") == 0
    assert _requests("/metrics", "200") == 0


# --- the booking flow ---------------------------------------------------------


async def test_holds_are_counted_by_outcome(client, tenant_a):
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    before = {o: _value("cinecloud_seat_holds_total", outcome=o)
              for o in ("placed", "unavailable", "invalid")}

    await client.post(f"{url}/holds", json={"seat_ids": [s1]})       # placed
    await client.post(f"{url}/holds", json={"seat_ids": [s1]})       # 409
    await client.post(f"{url}/holds", json={"seat_ids": [999_999]})  # 422

    for outcome in before:
        assert _value("cinecloud_seat_holds_total", outcome=outcome) == before[outcome] + 1


async def test_bookings_and_sold_seats_are_counted(client, tenant_a):
    url, _, (s1, s2, *_) = await _showtime(client, tenant_a)
    token = (await client.post(f"{url}/holds", json={"seat_ids": [s1, s2]})).json()["hold_token"]
    confirmed = _value("cinecloud_bookings_total", outcome="confirmed")
    expired = _value("cinecloud_bookings_total", outcome="expired")
    sold = _value("cinecloud_seats_sold_total")

    guest = {"guest_email": "anna@kino-alpha.de"}
    await client.post(f"{url}/bookings", json={"hold_token": token, **guest})
    await client.post(f"{url}/bookings", json={"hold_token": "unknown", **guest})

    assert _value("cinecloud_bookings_total", outcome="confirmed") == confirmed + 1
    assert _value("cinecloud_bookings_total", outcome="expired") == expired + 1
    assert _value("cinecloud_seats_sold_total") == sold + 2


async def test_open_seat_streams_are_tracked(client, session, redis, engine, tenant_a):
    _, showtime_id, _ = await _showtime(client, tenant_a)
    showtime = await session.get(Showtime, showtime_id)
    sessions = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    before = _value("cinecloud_seat_streams_open")

    stream = seat_events(redis, sessions, showtime)
    try:
        await asyncio.wait_for(anext(stream), timeout=5)  # the snapshot
        assert _value("cinecloud_seat_streams_open") == before + 1
    finally:
        await stream.aclose()

    assert _value("cinecloud_seat_streams_open") == before


async def test_redis_failures_are_counted_by_what_they_cost(client, tenant_a):
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    failed = _value("cinecloud_redis_failures_total", context="request")
    degraded = _value("cinecloud_redis_failures_total", context="seat_map")

    unreachable = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    app.dependency_overrides[get_redis] = lambda: unreachable
    try:
        await client.post(f"{url}/holds", json={"seat_ids": [s1]})  # 503
        await client.get(url)  # seat map without holds
    finally:
        await unreachable.aclose()

    assert _value("cinecloud_redis_failures_total", context="request") == failed + 1
    assert _value("cinecloud_redis_failures_total", context="seat_map") == degraded + 1
