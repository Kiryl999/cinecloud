"""Hall endpoints - seat grid generation and tenant isolation."""

HALL = {"name": "Saal 1", "rows": 3, "seats_per_row": 4}


async def test_create_materialises_the_seat_grid(client, tenant_a):
    """Without seats there is no Saalplan, so they are created with the hall."""
    response = await client.post("/halls/", json=HALL, headers=tenant_a.headers)

    assert response.status_code == 201
    body = response.json()
    assert body["cinema_id"] == tenant_a.cinema_id
    assert body["seat_count"] == 12

    positions = {(seat["row_number"], seat["seat_number"]) for seat in body["seats"]}
    assert positions == {(row, num) for row in range(1, 4) for num in range(1, 5)}


async def test_list_returns_only_own_halls(client, tenant_a, tenant_b):
    await client.post("/halls/", json=HALL, headers=tenant_a.headers)
    await client.post(
        "/halls/", json={**HALL, "name": "Beta hall"}, headers=tenant_b.headers
    )

    response = await client.get("/halls/", headers=tenant_a.headers)

    assert [hall["name"] for hall in response.json()] == [HALL["name"]]


async def test_read_of_foreign_hall_is_404(client, tenant_a, tenant_b):
    hall_id = (
        await client.post("/halls/", json=HALL, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.get(f"/halls/{hall_id}", headers=tenant_b.headers)

    assert response.status_code == 404


async def test_delete_of_foreign_hall_is_404(client, tenant_a, tenant_b):
    hall_id = (
        await client.post("/halls/", json=HALL, headers=tenant_a.headers)
    ).json()["id"]

    assert (
        await client.delete(f"/halls/{hall_id}", headers=tenant_b.headers)
    ).status_code == 404
    assert (
        await client.get(f"/halls/{hall_id}", headers=tenant_a.headers)
    ).status_code == 200


async def test_endpoints_require_authentication(client):
    assert (await client.get("/halls/")).status_code == 401


async def test_hall_with_showtimes_cannot_be_deleted(client, tenant_a):
    """409 instead of the 500 caused by orphaning the showtimes' seats."""
    hall_id = (
        await client.post("/halls/", json=HALL, headers=tenant_a.headers)
    ).json()["id"]
    movie_id = (
        await client.post(
            "/movies/",
            json={"title": "Arrival", "release_year": 2016, "duration_minutes": 116},
            headers=tenant_a.headers,
        )
    ).json()["id"]
    await client.post(
        "/showtimes/",
        json={
            "movie_id": movie_id,
            "hall_id": hall_id,
            "start_time": "2026-09-01T20:00:00+00:00",
            "ticket_price": "10.00",
        },
        headers=tenant_a.headers,
    )

    response = await client.delete(f"/halls/{hall_id}", headers=tenant_a.headers)

    assert response.status_code == 409
    assert (
        await client.get(f"/halls/{hall_id}", headers=tenant_a.headers)
    ).status_code == 200


async def test_owner_can_delete_an_unused_hall(client, tenant_a):
    hall_id = (
        await client.post("/halls/", json=HALL, headers=tenant_a.headers)
    ).json()["id"]

    assert (
        await client.delete(f"/halls/{hall_id}", headers=tenant_a.headers)
    ).status_code == 204
    assert (
        await client.get(f"/halls/{hall_id}", headers=tenant_a.headers)
    ).status_code == 404


async def test_renaming_to_null_is_422_not_500(client, tenant_a):
    hall_id = (
        await client.post("/halls/", json=HALL, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.patch(
        f"/halls/{hall_id}", json={"name": None}, headers=tenant_a.headers
    )

    assert response.status_code == 422
