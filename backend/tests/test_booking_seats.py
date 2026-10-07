"""The database's own guarantee against double-booking.

These tests write to booking_seats directly, below any application code. That
is the point of the constraints: they must hold even when everything above them
- holds, checks, a buggy endpoint - lets a second sale through.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.booking_seat import BookingSeat
from tests.conftest import sell_seats


async def _two_showtimes_in_one_hall(client, tenant):
    """Two showtimes in the same hall, so they share the same physical seats."""
    movie_id = (
        await client.post(
            "/movies/",
            json={"title": "Arrival", "release_year": 2016, "duration_minutes": 116},
            headers=tenant.headers,
        )
    ).json()["id"]
    hall = (
        await client.post(
            "/halls/",
            json={"name": "Saal 1", "rows": 1, "seats_per_row": 2},
            headers=tenant.headers,
        )
    ).json()

    showtime_ids = []
    for start in ("2030-01-01T20:00:00+00:00", "2030-01-02T20:00:00+00:00"):
        response = await client.post(
            "/showtimes/",
            json={
                "movie_id": movie_id,
                "hall_id": hall["id"],
                "start_time": start,
                "ticket_price": "10.00",
            },
            headers=tenant.headers,
        )
        showtime_ids.append(response.json()["id"])

    return showtime_ids, [seat["id"] for seat in hall["seats"]]


async def test_a_seat_is_sold_at_most_once_per_showtime(client, session, tenant_a):
    (showtime_id, _), (seat_id, _) = await _two_showtimes_in_one_hall(client, tenant_a)
    await sell_seats(
        session, cinema_id=tenant_a.cinema_id, showtime_id=showtime_id, seat_ids=[seat_id]
    )

    with pytest.raises(IntegrityError, match="uq_booking_seat_per_showtime"):
        await sell_seats(
            session,
            cinema_id=tenant_a.cinema_id,
            showtime_id=showtime_id,
            seat_ids=[seat_id],
        )
    await session.rollback()


async def test_the_same_seat_can_be_sold_once_per_showtime(client, session, tenant_a):
    """The constraint is per showtime - tomorrow the seat is for sale again."""
    showtime_ids, (seat_id, _) = await _two_showtimes_in_one_hall(client, tenant_a)

    for showtime_id in showtime_ids:
        await sell_seats(
            session,
            cinema_id=tenant_a.cinema_id,
            showtime_id=showtime_id,
            seat_ids=[seat_id],
        )


async def test_a_sold_seat_is_pinned_to_its_bookings_showtime(client, session, tenant_a):
    """booking_seats repeats the showtime; the composite key keeps both copies equal."""
    (first, second), (seat_a, seat_b) = await _two_showtimes_in_one_hall(client, tenant_a)
    booking_id = await sell_seats(
        session, cinema_id=tenant_a.cinema_id, showtime_id=first, seat_ids=[seat_a]
    )

    # a booking for the first showtime trying to claim a seat in the second one
    session.add(BookingSeat(booking_id=booking_id, showtime_id=second, seat_id=seat_b))

    with pytest.raises(IntegrityError, match="fk_booking_seats_booking"):
        await session.commit()
    await session.rollback()
