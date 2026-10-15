"""Public visitor endpoints: programme and seat map, no token involved.

Without a token the tenant comes from the slug in the path, so the isolation
cases here mirror the admin ones: a showtime must only be reachable under the
cinema it belongs to.
"""

from datetime import datetime, timedelta, timezone

from tests.conftest import sell_seats

MOVIE = {
    "title": "Past Lives",
    "description": "Two childhood friends meet again.",
    "release_year": 2023,
    "duration_minutes": 106,
}
HALL = {"name": "Saal 1", "rows": 2, "seats_per_row": 3}


def _from_now(**offset) -> str:
    # relative to the real clock: the public side only shows what is still ahead
    return (datetime.now(timezone.utc) + timedelta(**offset)).isoformat()


async def _schedule(client, tenant, *starts: str) -> list[int]:
    """Create one movie and one hall for `tenant` and a showtime at each start."""
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant.headers)
    ).json()["id"]
    hall_id = (
        await client.post("/halls/", json=HALL, headers=tenant.headers)
    ).json()["id"]

    ids = []
    for start in starts:
        response = await client.post(
            "/showtimes/",
            json={
                "movie_id": movie_id,
                "hall_id": hall_id,
                "start_time": start,
                "ticket_price": "11.00",
            },
            headers=tenant.headers,
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


async def test_cinema_is_found_by_slug(client, tenant_a):
    response = await client.get("/cinemas/kino-alpha")

    assert response.status_code == 200
    assert response.json()["id"] == tenant_a.cinema_id


async def test_unknown_slug_is_404(client, tenant_a):
    assert (await client.get("/cinemas/nowhere")).status_code == 404
    assert (await client.get("/cinemas/nowhere/showtimes")).status_code == 404


async def test_programme_lists_upcoming_showtimes_in_order(client, tenant_a):
    """No token needed, past showtimes left out, soonest first."""
    later, past, sooner = await _schedule(
        client,
        tenant_a,
        _from_now(days=2),
        _from_now(days=-2),
        _from_now(days=1),
    )

    response = await client.get("/cinemas/kino-alpha/showtimes")

    assert response.status_code == 200
    body = response.json()
    assert [showtime["id"] for showtime in body] == [sooner, later]
    assert body[0]["movie"]["title"] == MOVIE["title"]
    assert body[0]["hall"]["name"] == HALL["name"]


async def test_programme_does_not_mix_cinemas(client, tenant_a, tenant_b):
    await _schedule(client, tenant_b, _from_now(days=1))

    response = await client.get("/cinemas/kino-alpha/showtimes")

    assert response.json() == []


async def test_showtime_is_only_found_under_its_own_cinema(client, tenant_a, tenant_b):
    (foreign,) = await _schedule(client, tenant_b, _from_now(days=1))

    response = await client.get(f"/cinemas/kino-alpha/showtimes/{foreign}")

    assert response.status_code == 404


async def test_started_showtime_has_no_seat_map(client, tenant_a):
    (past,) = await _schedule(client, tenant_a, _from_now(hours=-1))

    response = await client.get(f"/cinemas/kino-alpha/showtimes/{past}")

    assert response.status_code == 404


async def test_seat_map_lists_every_seat_in_order(client, tenant_a):
    (showtime_id,) = await _schedule(client, tenant_a, _from_now(days=1))

    response = await client.get(f"/cinemas/kino-alpha/showtimes/{showtime_id}")

    assert response.status_code == 200
    seats = response.json()["seats"]
    assert [(s["row_number"], s["seat_number"]) for s in seats] == [
        (row, number) for row in range(1, 3) for number in range(1, 4)
    ]
    assert {s["status"] for s in seats} == {"available"}


async def test_seat_map_marks_sold_seats_as_booked(client, session, tenant_a):
    (showtime_id,) = await _schedule(client, tenant_a, _from_now(days=1))
    url = f"/cinemas/kino-alpha/showtimes/{showtime_id}"
    sold, free = [s["id"] for s in (await client.get(url)).json()["seats"][:2]]
    await sell_seats(
        session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=[sold]
    )

    status = {s["id"]: s["status"] for s in (await client.get(url)).json()["seats"]}

    assert status[sold] == "booked"
    assert status[free] == "available"


async def test_seat_sold_for_another_showtime_is_free_in_this_one(
    client, session, tenant_a
):
    """A physical seat is sold per showtime, not once and for all."""
    earlier, later = await _schedule(
        client, tenant_a, _from_now(days=1), _from_now(days=2)
    )
    seat_id = (
        await client.get(f"/cinemas/kino-alpha/showtimes/{earlier}")
    ).json()["seats"][0]["id"]
    await sell_seats(
        session, cinema_id=tenant_a.cinema_id, showtime_id=earlier, seat_ids=[seat_id]
    )

    later_seats = (await client.get(f"/cinemas/kino-alpha/showtimes/{later}")).json()

    assert {s["id"]: s["status"] for s in later_seats["seats"]}[seat_id] == "available"


async def test_seat_map_exposes_no_internal_fields(client, tenant_a):
    """Booking ids and hold tokens stay on the server - a token would let anyone book."""
    (showtime_id,) = await _schedule(client, tenant_a, _from_now(days=1))

    body = (await client.get(f"/cinemas/kino-alpha/showtimes/{showtime_id}")).json()

    assert set(body["seats"][0]) == {
        "id", "row_number", "seat_number", "status", "hold_expires_in",
    }
    assert "cinema_id" not in body
