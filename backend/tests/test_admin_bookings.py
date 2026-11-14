"""The cinema's view of its sales: bookings, seats sold per showtime, and the
seat map of any showtime, past ones included.

Bookings are written straight to the database (sell_seats) where the booking
flow itself is not the point - test_booking.py covers that.
"""

from datetime import datetime, timedelta, timezone

from app.services import seat_holds
from tests.conftest import sell_seats

MOVIE = {"title": "Arrival", "release_year": 2016, "duration_minutes": 116}
HALL = {"name": "Saal 1", "rows": 2, "seats_per_row": 3}


async def _showtime(client, tenant, *, days_ahead: int = 1) -> tuple[int, list[int]]:
    """A showtime `days_ahead` from now, negative for the past; returns its id
    and its hall's seat ids, ordered by row and number."""
    movie_id = (await client.post("/movies/", json=MOVIE, headers=tenant.headers)).json()["id"]
    hall = (await client.post("/halls/", json=HALL, headers=tenant.headers)).json()
    start = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    response = await client.post(
        "/showtimes/",
        json={
            "movie_id": movie_id,
            "hall_id": hall["id"],
            "start_time": start.isoformat(),
            "ticket_price": "10.00",
        },
        headers=tenant.headers,
    )
    return response.json()["id"], [seat["id"] for seat in hall["seats"]]


# --- the list of bookings ----------------------------------------------------


async def test_bookings_come_newest_first_with_their_seats(client, session, tenant_a):
    showtime_id, seats = await _showtime(client, tenant_a)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=seats[4:6])
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=seats[:1])

    response = await client.get("/bookings/", headers=tenant_a.headers)

    assert response.status_code == 200
    newest, older = response.json()
    assert [(s["row_number"], s["seat_number"]) for s in newest["seats"]] == [(1, 1)]
    assert [(s["row_number"], s["seat_number"]) for s in older["seats"]] == [(2, 2), (2, 3)]
    assert older["seats"][0]["id"] == seats[4]
    assert older["total_price"] == "20.00"
    assert older["showtime_id"] == showtime_id
    assert older["guest_email"] == "guest@kino-alpha.de"
    assert older["status"] == "confirmed"
    assert newest["created_at"] >= older["created_at"]


async def test_bookings_of_other_cinemas_stay_hidden(client, session, tenant_a, tenant_b):
    showtime_id, seats = await _showtime(client, tenant_a)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=seats[:2])

    assert (await client.get("/bookings/", headers=tenant_b.headers)).json() == []
    # naming the showtime does not help either
    response = await client.get(
        "/bookings/", params={"showtime_id": showtime_id}, headers=tenant_b.headers
    )
    assert response.json() == []


async def test_bookings_need_a_signed_in_admin(client):
    assert (await client.get("/bookings/")).status_code == 401


async def test_bookings_of_one_showtime(client, session, tenant_a):
    first, first_seats = await _showtime(client, tenant_a, days_ahead=1)
    second, second_seats = await _showtime(client, tenant_a, days_ahead=2)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=first, seat_ids=first_seats[:1])
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=second, seat_ids=second_seats[:1])

    response = await client.get(
        "/bookings/", params={"showtime_id": second}, headers=tenant_a.headers
    )

    assert [booking["showtime_id"] for booking in response.json()] == [second]


async def test_a_booking_is_found_by_its_reference_or_the_guests_address(
    client, session, tenant_a
):
    showtime_id, seats = await _showtime(client, tenant_a)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=seats[:1])
    reference = (await client.get("/bookings/", headers=tenant_a.headers)).json()[0]["reference"]

    async def search(term):
        response = await client.get("/bookings/", params={"q": term}, headers=tenant_a.headers)
        return [booking["reference"] for booking in response.json()]

    # as read out on the phone: in lower case, with blanks around it
    assert await search(f" {reference.lower()} ") == [reference]
    assert await search("GUEST@kino") == [reference]
    assert await search("nobody") == []
    # a wildcard is just a character in the address, not a pattern
    assert await search("%") == []


async def test_the_list_is_cut_at_the_limit(client, session, tenant_a):
    showtime_id, seats = await _showtime(client, tenant_a)
    for seat in seats[:3]:
        await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=[seat])

    response = await client.get("/bookings/", params={"limit": 2}, headers=tenant_a.headers)

    assert len(response.json()) == 2
    too_many = await client.get("/bookings/", params={"limit": 5000}, headers=tenant_a.headers)
    assert too_many.status_code == 422


# --- seats sold per showtime -------------------------------------------------


async def test_the_showtime_list_counts_seats_sold(client, session, tenant_a):
    sold_out, seats = await _showtime(client, tenant_a, days_ahead=1)
    empty, _ = await _showtime(client, tenant_a, days_ahead=2)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=sold_out, seat_ids=seats[:2])
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=sold_out, seat_ids=seats[2:])

    response = await client.get("/showtimes/", headers=tenant_a.headers)

    assert {s["id"]: s["seats_sold"] for s in response.json()} == {sold_out: 6, empty: 0}


# --- the seat map ------------------------------------------------------------


async def test_the_seat_map_shows_sold_held_and_free_seats(client, session, redis, tenant_a):
    showtime_id, seats = await _showtime(client, tenant_a)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=[seats[0]])
    await seat_holds.place(redis, showtime_id, [seats[1]])

    response = await client.get(f"/showtimes/{showtime_id}/seats", headers=tenant_a.headers)

    assert response.status_code == 200
    states = {seat["id"]: seat for seat in response.json()}
    assert states[seats[0]]["status"] == "booked"
    assert states[seats[1]]["status"] == "held"
    assert 0 < states[seats[1]]["hold_expires_in"] <= seat_holds.HOLD_SECONDS
    assert [states[seat]["status"] for seat in seats[2:]] == ["available"] * 4


async def test_the_seat_map_is_there_for_past_showtimes_too(client, session, tenant_a):
    showtime_id, seats = await _showtime(client, tenant_a, days_ahead=-1)
    await sell_seats(session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=seats[:3])

    response = await client.get(f"/showtimes/{showtime_id}/seats", headers=tenant_a.headers)

    assert [seat["status"] for seat in response.json()] == ["booked"] * 3 + ["available"] * 3


async def test_the_seat_map_of_another_cinemas_showtime_is_404(client, tenant_a, tenant_b):
    showtime_id, _ = await _showtime(client, tenant_a)

    response = await client.get(f"/showtimes/{showtime_id}/seats", headers=tenant_b.headers)

    assert response.status_code == 404
