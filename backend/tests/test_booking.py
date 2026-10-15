"""Guest booking: holds in Redis, sales in PostgreSQL, changes over SSE.

Grouped the way the booking sequence runs: reserving, booking, the live seat
stream, concurrency, and what happens when Redis is not there.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.booking import seat_events
from app.core.redis import get_redis
from app.main import app
from app.models.showtime import Showtime
from app.services import seat_holds
from tests.conftest import sell_seats

MOVIE = {"title": "Arrival", "release_year": 2016, "duration_minutes": 116}
HALL = {"name": "Saal 1", "rows": 2, "seats_per_row": 3}


async def _showtime(client, tenant) -> tuple[str, int, list[int]]:
    """A showtime tomorrow; returns its public URL, its id and the hall's seat ids."""
    movie_id = (await client.post("/movies/", json=MOVIE, headers=tenant.headers)).json()["id"]
    hall = (await client.post("/halls/", json=HALL, headers=tenant.headers)).json()
    showtime_id = (
        await client.post(
            "/showtimes/",
            json={
                "movie_id": movie_id,
                "hall_id": hall["id"],
                "start_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "ticket_price": "12.50",
            },
            headers=tenant.headers,
        )
    ).json()["id"]
    url = f"/cinemas/kino-alpha/showtimes/{showtime_id}"
    return url, showtime_id, [seat["id"] for seat in hall["seats"]]


async def _seat_states(client, url) -> dict[int, dict]:
    return {seat["id"]: seat for seat in (await client.get(url)).json()["seats"]}


# --- reserving ---------------------------------------------------------------


async def test_a_hold_reserves_the_seats_for_ten_minutes(client, tenant_a):
    url, _, (s1, s2, s3, *_) = await _showtime(client, tenant_a)

    response = await client.post(f"{url}/holds", json={"seat_ids": [s2, s1]})

    assert response.status_code == 201
    hold = response.json()
    assert hold["seat_ids"] == [s1, s2]
    assert hold["expires_in"] == 600
    assert len(hold["hold_token"]) >= 32  # unguessable

    seats = await _seat_states(client, url)
    assert seats[s1]["status"] == seats[s2]["status"] == "held"
    assert 590 < seats[s1]["hold_expires_in"] <= 600
    assert seats[s3]["status"] == "available"
    assert seats[s3]["hold_expires_in"] is None


async def test_a_held_seat_cannot_be_held_again(client, tenant_a):
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    await client.post(f"{url}/holds", json={"seat_ids": [s1]})

    response = await client.post(f"{url}/holds", json={"seat_ids": [s1]})

    assert response.status_code == 409


async def test_a_hold_is_all_or_nothing(client, tenant_a):
    """One taken seat and none of the requested seats is held."""
    url, _, (s1, s2, *_) = await _showtime(client, tenant_a)
    await client.post(f"{url}/holds", json={"seat_ids": [s1]})

    response = await client.post(f"{url}/holds", json={"seat_ids": [s1, s2]})

    assert response.status_code == 409
    assert (await _seat_states(client, url))[s2]["status"] == "available"


async def test_a_sold_seat_cannot_be_held(client, session, tenant_a):
    """Redis knows nothing about sales - the database is asked first."""
    url, showtime_id, (s1, *_) = await _showtime(client, tenant_a)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=[s1])

    response = await client.post(f"{url}/holds", json={"seat_ids": [s1]})

    assert response.status_code == 409


async def test_a_seat_of_another_hall_is_rejected(client, tenant_a):
    url, _, _ = await _showtime(client, tenant_a)
    other_hall = (
        await client.post("/halls/", json={**HALL, "name": "Saal 2"}, headers=tenant_a.headers)
    ).json()

    response = await client.post(
        f"{url}/holds", json={"seat_ids": [other_hall["seats"][0]["id"]]}
    )

    assert response.status_code == 422


async def test_one_request_cannot_hold_more_than_ten_seats(client, tenant_a):
    url, _, _ = await _showtime(client, tenant_a)

    response = await client.post(f"{url}/holds", json={"seat_ids": list(range(1, 12))})

    assert response.status_code == 422


async def test_holds_only_exist_for_showtimes_of_this_cinema(client, tenant_a, tenant_b):
    _, foreign_id, foreign_seats = await _showtime(client, tenant_b)

    response = await client.post(
        f"/cinemas/kino-alpha/showtimes/{foreign_id}/holds",
        json={"seat_ids": foreign_seats[:1]},
    )

    assert response.status_code == 404


# --- booking -----------------------------------------------------------------


async def test_booking_turns_a_hold_into_a_sale(client, redis, tenant_a, caplog):
    url, _, (s1, s2, *_) = await _showtime(client, tenant_a)
    token = (await client.post(f"{url}/holds", json={"seat_ids": [s1, s2]})).json()["hold_token"]

    with caplog.at_level(logging.INFO, logger="cinecloud.mail"):
        response = await client.post(
            f"{url}/bookings", json={"hold_token": token, "guest_email": "anna@kino-alpha.de"}
        )

    assert response.status_code == 201
    sale = response.json()
    assert len(sale["reference"]) == 8
    assert sale["seat_ids"] == [s1, s2]
    assert sale["total_price"] == "25.00"
    assert sale["status"] == "confirmed"

    seats = await _seat_states(client, url)
    assert seats[s1]["status"] == seats[s2]["status"] == "booked"
    # the hold is gone - the sale lives in PostgreSQL only
    assert await redis.keys("hold:*") == []

    # confirmation sent, without spreading the full address through the logs
    assert sale["reference"] in caplog.text
    assert "anna@kino-alpha.de" not in caplog.text


async def test_booking_with_an_unknown_token_is_409(client, tenant_a):
    url, _, _ = await _showtime(client, tenant_a)

    response = await client.post(
        f"{url}/bookings", json={"hold_token": "made-up", "guest_email": "anna@kino-alpha.de"}
    )

    assert response.status_code == 409


async def test_booking_after_the_hold_expired_is_409(client, redis, tenant_a):
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    token = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
    await redis.flushdb()  # what the TTL does after ten minutes

    response = await client.post(
        f"{url}/bookings", json={"hold_token": token, "guest_email": "anna@kino-alpha.de"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Reservation expired"


async def test_a_late_guest_cannot_book_a_seat_someone_else_holds_now(client, redis, tenant_a):
    """The token is what protects the hold - not the seat number."""
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    late = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
    await redis.flushdb()  # A's hold runs out
    current = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]

    too_late = await client.post(
        f"{url}/bookings", json={"hold_token": late, "guest_email": "anna@kino-alpha.de"}
    )
    in_time = await client.post(
        f"{url}/bookings", json={"hold_token": current, "guest_email": "ben@kino-alpha.de"}
    )

    assert too_late.status_code == 409
    assert in_time.status_code == 201


async def test_a_token_whose_seat_was_taken_over_cannot_book(client, redis, tenant_a):
    """Redis expires keys one by one, not a hold as a whole.

    If a seat key runs out a moment before its token key and another guest
    holds the seat in that moment, the old token still exists - but must no
    longer be able to book a seat that now belongs to someone else.
    """
    url, showtime_id, (s1, *_) = await _showtime(client, tenant_a)
    old = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
    await redis.delete(f"hold:{{{showtime_id}}}:seat:{s1}")  # only the seat key expired
    new = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]

    stale = await client.post(
        f"{url}/bookings", json={"hold_token": old, "guest_email": "anna@kino-alpha.de"}
    )
    current = await client.post(
        f"{url}/bookings", json={"hold_token": new, "guest_email": "ben@kino-alpha.de"}
    )

    assert stale.status_code == 409
    assert current.status_code == 201


async def test_securing_a_hold_raises_its_lifetime_but_never_extends_it(client, redis, tenant_a):
    """At least the confirm window - repeated attempts must not keep seats forever."""
    url, showtime_id, (s1, *_) = await _showtime(client, tenant_a)
    token = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
    keys = await redis.keys("hold:*")

    # plenty of time left: securing must not touch it
    await seat_holds.secure(redis, showtime_id, token)
    assert all(500_000 < ttl <= 600_000 for ttl in [await redis.pttl(k) for k in keys])

    # one second left: raised to the confirm window, and not beyond on repeat
    for key in keys:
        await redis.pexpire(key, 1_000)
    for _ in range(3):
        assert await seat_holds.secure(redis, showtime_id, token) == [s1]
    assert all(55_000 < ttl <= 60_000 for ttl in [await redis.pttl(k) for k in keys])


async def test_the_database_catches_a_hold_that_should_not_exist(client, redis, tenant_a):
    """The last line of defence: a seat sold although Redis let a hold through.

    That happens if Redis loses a key in a failover. The booking must fail with
    409 rather than 500 - and there must be nothing to undo in Redis.
    """
    url, showtime_id, (s1, *_) = await _showtime(client, tenant_a)
    first = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
    await client.post(f"{url}/bookings", json={"hold_token": first, "guest_email": "anna@kino-alpha.de"})

    # a hold placed straight in Redis, past the database check
    ghost = await seat_holds.place(redis, showtime_id, [s1])

    response = await client.post(
        f"{url}/bookings", json={"hold_token": ghost.token, "guest_email": "ben@kino-alpha.de"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Seats already sold"
    assert await redis.keys("hold:*") != []  # untouched, it simply runs out
    assert (await _seat_states(client, url))[s1]["status"] == "booked"  # sold beats held


# --- live seat stream --------------------------------------------------------


async def _next_event(stream) -> tuple[str, dict]:
    """The next real event from an SSE stream, skipping keep-alive comments."""
    while True:
        chunk = await asyncio.wait_for(anext(stream), timeout=5)
        if not chunk.startswith(":"):
            name_line, data_line = chunk.strip().split("\n")
            return name_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))


async def test_the_stream_starts_with_the_current_seat_map(client, session, redis, engine, tenant_a):
    url, showtime_id, (s1, s2, *_) = await _showtime(client, tenant_a)
    await client.post(f"{url}/holds", json={"seat_ids": [s1]})
    showtime = await session.get(Showtime, showtime_id)
    sessions = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    stream = seat_events(redis, sessions, showtime)
    try:
        name, data = await _next_event(stream)
    finally:
        await stream.aclose()

    seats = {seat["id"]: seat for seat in data["seats"]}
    assert name == "snapshot"
    assert seats[s1]["status"] == "held"
    assert seats[s1]["hold_expires_in"] > 590
    assert seats[s2]["status"] == "available"


async def test_the_stream_forwards_changes_and_keeps_quiet_connections_alive(
    client, session, redis, engine, tenant_a
):
    url, showtime_id, (s1, *_) = await _showtime(client, tenant_a)
    showtime = await session.get(Showtime, showtime_id)
    sessions = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    stream = seat_events(redis, sessions, showtime, keepalive_seconds=0.1)
    try:
        assert (await _next_event(stream))[0] == "snapshot"
        assert (await asyncio.wait_for(anext(stream), timeout=5)) == ": keep-alive\n\n"

        token = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
        assert await _next_event(stream) == (
            "seats", {"event": "held", "seat_ids": [s1], "expires_in": 600}
        )

        await client.post(
            f"{url}/bookings", json={"hold_token": token, "guest_email": "anna@kino-alpha.de"}
        )
        assert await _next_event(stream) == ("seats", {"event": "booked", "seat_ids": [s1]})
    finally:
        await stream.aclose()


async def test_a_failed_hold_announces_nothing(client, redis, tenant_a):
    url, showtime_id, (s1, *_) = await _showtime(client, tenant_a)
    await client.post(f"{url}/holds", json={"seat_ids": [s1]})
    pubsub = redis.pubsub()
    await pubsub.subscribe(seat_holds.channel(showtime_id))
    await pubsub.get_message(timeout=1)  # subscription confirmed

    await client.post(f"{url}/holds", json={"seat_ids": [s1]})  # 409

    assert await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5) is None
    await pubsub.aclose()


async def test_the_stream_is_only_offered_for_upcoming_showtimes(client, tenant_a):
    response = await client.get("/cinemas/kino-alpha/showtimes/999/seats/stream")

    assert response.status_code == 404


# --- concurrency and outages ---------------------------------------------------


async def test_two_guests_holding_the_same_seat_at_once_get_one_hold(
    client, tenant_a, session_per_request
):
    url, _, (s1, *_) = await _showtime(client, tenant_a)

    responses = await asyncio.gather(
        client.post(f"{url}/holds", json={"seat_ids": [s1]}),
        client.post(f"{url}/holds", json={"seat_ids": [s1]}),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]


async def test_without_redis_reserving_fails_cleanly_and_the_seat_map_degrades(
    client, tenant_a
):
    """Holds cannot work without Redis: 503, not 500. Reading still works."""
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    unreachable = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    app.dependency_overrides[get_redis] = lambda: unreachable
    try:
        hold = await client.post(f"{url}/holds", json={"seat_ids": [s1]})
        seat_map = await client.get(url)
    finally:
        await unreachable.aclose()

    assert hold.status_code == 503
    assert seat_map.status_code == 200
    assert {seat["status"] for seat in seat_map.json()["seats"]} == {"available"}
