"""Showtime endpoints.

Two groups of cases. The foreign-key ones: a showtime points at a movie and a
hall, and the database's foreign keys would happily accept ids belonging to a
different cinema - only the tenant scope prevents that. And the scheduling
ones: a hall shows one film at a time, followed by a turnaround.
"""

import asyncio
from datetime import datetime, timedelta

from app.api.scheduling import TURNAROUND_MINUTES
from tests.conftest import sell_seats

MOVIE = {
    "title": "Arrival",
    "description": "Linguist meets heptapods.",
    "release_year": 2016,
    "duration_minutes": 116,
}
HALL = {"name": "Saal 1", "rows": 2, "seats_per_row": 3}
START = "2026-09-01T20:00:00+00:00"


async def _movie_id(client, tenant) -> int:
    response = await client.post("/movies/", json=MOVIE, headers=tenant.headers)
    return response.json()["id"]


async def _hall_id(client, tenant) -> int:
    response = await client.post("/halls/", json=HALL, headers=tenant.headers)
    return response.json()["id"]


def _payload(movie_id: int, hall_id: int, start: str = START) -> dict:
    return {
        "movie_id": movie_id,
        "hall_id": hall_id,
        "start_time": start,
        "ticket_price": "12.50",
    }


def _at(minutes: int) -> str:
    """START shifted by `minutes`, in the ISO format the API expects."""
    return (datetime.fromisoformat(START) + timedelta(minutes=minutes)).isoformat()


# how long one showtime of MOVIE blocks its hall
SLOT_MINUTES = MOVIE["duration_minutes"] + TURNAROUND_MINUTES


async def test_create_schedules_into_the_callers_cinema(client, tenant_a):
    movie_id = await _movie_id(client, tenant_a)
    hall_id = await _hall_id(client, tenant_a)

    response = await client.post(
        "/showtimes/", json=_payload(movie_id, hall_id), headers=tenant_a.headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["cinema_id"] == tenant_a.cinema_id
    assert (body["movie_id"], body["hall_id"]) == (movie_id, hall_id)


async def test_cannot_schedule_onto_foreign_movie(client, tenant_a, tenant_b):
    payload = _payload(
        await _movie_id(client, tenant_b),  # belongs to the other cinema
        await _hall_id(client, tenant_a),
    )

    response = await client.post("/showtimes/", json=payload, headers=tenant_a.headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found"


async def test_cannot_schedule_into_foreign_hall(client, tenant_a, tenant_b):
    payload = _payload(
        await _movie_id(client, tenant_a),
        await _hall_id(client, tenant_b),  # belongs to the other cinema
    )

    response = await client.post("/showtimes/", json=payload, headers=tenant_a.headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Hall not found"


async def test_list_returns_only_own_showtimes(client, tenant_a, tenant_b):
    await client.post(
        "/showtimes/",
        json=_payload(
            await _movie_id(client, tenant_a), await _hall_id(client, tenant_a)
        ),
        headers=tenant_a.headers,
    )
    await client.post(
        "/showtimes/",
        json=_payload(
            await _movie_id(client, tenant_b), await _hall_id(client, tenant_b)
        ),
        headers=tenant_b.headers,
    )

    response = await client.get("/showtimes/", headers=tenant_a.headers)

    body = response.json()
    assert len(body) == 1
    assert body[0]["cinema_id"] == tenant_a.cinema_id


async def test_read_of_foreign_showtime_is_404(client, tenant_a, tenant_b):
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(
                await _movie_id(client, tenant_a), await _hall_id(client, tenant_a)
            ),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.get(f"/showtimes/{showtime_id}", headers=tenant_b.headers)

    assert response.status_code == 404


async def test_patch_cannot_move_the_showtime_to_another_hall(client, tenant_a):
    """hall_id is not part of ShowtimeUpdate - the seats are already materialised."""
    hall_id = await _hall_id(client, tenant_a)
    other_hall = (
        await client.post(
            "/halls/", json={**HALL, "name": "Saal 2"}, headers=tenant_a.headers
        )
    ).json()["id"]
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(await _movie_id(client, tenant_a), hall_id),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.patch(
        f"/showtimes/{showtime_id}",
        json={"hall_id": other_hall},
        headers=tenant_a.headers,
    )

    assert response.status_code == 200
    assert response.json()["hall_id"] == hall_id


async def test_patch_cannot_point_at_a_foreign_movie(client, tenant_a, tenant_b):
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(
                await _movie_id(client, tenant_a), await _hall_id(client, tenant_a)
            ),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.patch(
        f"/showtimes/{showtime_id}",
        json={"movie_id": await _movie_id(client, tenant_b)},
        headers=tenant_a.headers,
    )

    assert response.status_code == 404


async def test_endpoints_require_authentication(client):
    assert (await client.get("/showtimes/")).status_code == 401


async def test_showtime_with_bookings_cannot_be_deleted(client, session, tenant_a):
    """409 rather than a 500 - and sold tickets must never vanish with it."""
    hall_id = await _hall_id(client, tenant_a)
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(await _movie_id(client, tenant_a), hall_id),
            headers=tenant_a.headers,
        )
    ).json()["id"]
    seats = (await client.get(f"/halls/{hall_id}", headers=tenant_a.headers)).json()["seats"]
    await sell_seats(
        session,
        cinema_id=tenant_a.cinema_id,
        showtime_id=showtime_id,
        seat_ids=[seats[0]["id"]],
    )

    response = await client.delete(f"/showtimes/{showtime_id}", headers=tenant_a.headers)

    assert response.status_code == 409
    assert (
        await client.get(f"/showtimes/{showtime_id}", headers=tenant_a.headers)
    ).status_code == 200


async def test_showtime_without_bookings_can_be_deleted(client, tenant_a):
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(
                await _movie_id(client, tenant_a), await _hall_id(client, tenant_a)
            ),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    assert (
        await client.delete(f"/showtimes/{showtime_id}", headers=tenant_a.headers)
    ).status_code == 204
    assert (
        await client.get(f"/showtimes/{showtime_id}", headers=tenant_a.headers)
    ).status_code == 404

# --- scheduling ---------------------------------------------------------------


async def test_start_time_without_utc_offset_is_rejected(client, tenant_a):
    """Otherwise the server's own time zone would decide what gets stored."""
    payload = _payload(
        await _movie_id(client, tenant_a),
        await _hall_id(client, tenant_a),
        start="2026-09-01T20:00",  # what <input type="datetime-local"> produces
    )

    response = await client.post("/showtimes/", json=payload, headers=tenant_a.headers)

    assert response.status_code == 422


async def test_overlapping_showtime_in_the_same_hall_is_409(client, tenant_a):
    movie_id = await _movie_id(client, tenant_a)
    hall_id = await _hall_id(client, tenant_a)
    await client.post(
        "/showtimes/", json=_payload(movie_id, hall_id), headers=tenant_a.headers
    )

    response = await client.post(
        "/showtimes/",
        json=_payload(movie_id, hall_id, start=_at(60)),
        headers=tenant_a.headers,
    )

    assert response.status_code == 409


async def test_hall_is_free_again_only_after_film_and_turnaround(client, tenant_a):
    """Boundaries in both directions: after the existing showtime and before it."""
    movie_id = await _movie_id(client, tenant_a)
    hall_id = await _hall_id(client, tenant_a)
    await client.post(
        "/showtimes/", json=_payload(movie_id, hall_id), headers=tenant_a.headers
    )

    async def schedule_at(minutes: int) -> int:
        response = await client.post(
            "/showtimes/",
            json=_payload(movie_id, hall_id, start=_at(minutes)),
            headers=tenant_a.headers,
        )
        return response.status_code

    assert await schedule_at(SLOT_MINUTES - 1) == 409
    assert await schedule_at(SLOT_MINUTES) == 201
    # a showtime before it must be over, turnaround included, by START
    assert await schedule_at(-SLOT_MINUTES + 1) == 409
    assert await schedule_at(-SLOT_MINUTES) == 201


async def test_the_same_slot_in_another_hall_is_fine(client, tenant_a):
    movie_id = await _movie_id(client, tenant_a)
    first_hall = await _hall_id(client, tenant_a)
    second_hall = (
        await client.post(
            "/halls/", json={**HALL, "name": "Saal 2"}, headers=tenant_a.headers
        )
    ).json()["id"]
    await client.post(
        "/showtimes/", json=_payload(movie_id, first_hall), headers=tenant_a.headers
    )

    response = await client.post(
        "/showtimes/", json=_payload(movie_id, second_hall), headers=tenant_a.headers
    )

    assert response.status_code == 201


async def test_moving_a_showtime_into_an_occupied_slot_is_409(client, tenant_a):
    movie_id = await _movie_id(client, tenant_a)
    hall_id = await _hall_id(client, tenant_a)
    await client.post(
        "/showtimes/", json=_payload(movie_id, hall_id), headers=tenant_a.headers
    )
    later_id = (
        await client.post(
            "/showtimes/",
            json=_payload(movie_id, hall_id, start=_at(SLOT_MINUTES)),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.patch(
        f"/showtimes/{later_id}", json={"start_time": _at(30)}, headers=tenant_a.headers
    )

    assert response.status_code == 409


async def test_moving_a_showtime_slightly_does_not_clash_with_itself(client, tenant_a):
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(
                await _movie_id(client, tenant_a), await _hall_id(client, tenant_a)
            ),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.patch(
        f"/showtimes/{showtime_id}", json={"start_time": _at(10)}, headers=tenant_a.headers
    )

    assert response.status_code == 200


async def test_rescheduling_to_null_is_422_not_500(client, tenant_a):
    showtime_id = (
        await client.post(
            "/showtimes/",
            json=_payload(
                await _movie_id(client, tenant_a), await _hall_id(client, tenant_a)
            ),
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.patch(
        f"/showtimes/{showtime_id}", json={"start_time": None}, headers=tenant_a.headers
    )

    assert response.status_code == 422


async def test_a_longer_duration_that_would_overlap_the_next_showtime_is_409(
    client, tenant_a
):
    """A showtime's end follows from its movie, so a duration change moves it."""
    movie_id = await _movie_id(client, tenant_a)
    hall_id = await _hall_id(client, tenant_a)
    for start in (START, _at(SLOT_MINUTES)):  # back to back, no minute to spare
        await client.post(
            "/showtimes/",
            json=_payload(movie_id, hall_id, start=start),
            headers=tenant_a.headers,
        )

    response = await client.patch(
        f"/movies/{movie_id}",
        json={"duration_minutes": MOVIE["duration_minutes"] + 1},
        headers=tenant_a.headers,
    )

    assert response.status_code == 409
    movie = (await client.get(f"/movies/{movie_id}", headers=tenant_a.headers)).json()
    assert movie["duration_minutes"] == MOVIE["duration_minutes"]


async def test_concurrent_requests_cannot_double_book_a_slot(
    client, tenant_a, session_per_request
):
    """Two admins scheduling different films into the same slot at once.

    Without the schedule lock both requests pass the overlap check before
    either has committed - a check-then-act race - and both showtimes land.
    """
    hall_id = await _hall_id(client, tenant_a)
    arrival = await _movie_id(client, tenant_a)
    contact = (
        await client.post(
            "/movies/", json={**MOVIE, "title": "Contact"}, headers=tenant_a.headers
        )
    ).json()["id"]

    responses = await asyncio.gather(
        client.post(
            "/showtimes/", json=_payload(arrival, hall_id), headers=tenant_a.headers
        ),
        client.post(
            "/showtimes/", json=_payload(contact, hall_id), headers=tenant_a.headers
        ),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
