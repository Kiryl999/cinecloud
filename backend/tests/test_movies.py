"""Tenant isolation for the movie endpoints.

None of these cases guard a feature - a missing `.where(cinema_id == ...)` would
break nothing visible. They guard the one invariant that has no visible symptom
when it fails: cinema A must never reach cinema B's data.
"""

MOVIE = {
    "title": "Dune: Part Two",
    "description": "Paul Atreides unites with the Fremen.",
    "release_year": 2024,
    "duration_minutes": 166,
}


async def test_create_takes_tenant_from_token(client, tenant_a):
    response = await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)

    assert response.status_code == 201
    assert response.json()["cinema_id"] == tenant_a.cinema_id


async def test_cinema_id_in_body_is_ignored(client, tenant_a, tenant_b):
    """A client that supplies a foreign cinema_id must not be able to plant data."""
    response = await client.post(
        "/movies/",
        json={**MOVIE, "cinema_id": tenant_b.cinema_id},
        headers=tenant_a.headers,
    )

    assert response.status_code == 201
    assert response.json()["cinema_id"] == tenant_a.cinema_id


async def test_list_returns_only_own_movies(client, tenant_a, tenant_b):
    await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    await client.post(
        "/movies/", json={**MOVIE, "title": "Beta exclusive"}, headers=tenant_b.headers
    )

    response = await client.get("/movies/", headers=tenant_a.headers)

    assert [movie["title"] for movie in response.json()] == [MOVIE["title"]]


async def test_read_of_foreign_movie_is_404(client, tenant_a, tenant_b):
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.get(f"/movies/{movie_id}", headers=tenant_b.headers)

    # 404 and not 403: a 403 would confirm that this id exists and turn the
    # endpoint into an oracle for probing another tenant's key space
    assert response.status_code == 404


async def test_update_of_foreign_movie_is_404_and_changes_nothing(
    client, tenant_a, tenant_b
):
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.patch(
        f"/movies/{movie_id}", json={"title": "Hijacked"}, headers=tenant_b.headers
    )
    assert response.status_code == 404

    still_there = await client.get(f"/movies/{movie_id}", headers=tenant_a.headers)
    assert still_there.json()["title"] == MOVIE["title"]


async def test_delete_of_foreign_movie_is_404_and_keeps_the_row(
    client, tenant_a, tenant_b
):
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.delete(f"/movies/{movie_id}", headers=tenant_b.headers)
    assert response.status_code == 404

    assert (
        await client.get(f"/movies/{movie_id}", headers=tenant_a.headers)
    ).status_code == 200


async def test_owner_can_delete_own_movie(client, tenant_a):
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]

    assert (
        await client.delete(f"/movies/{movie_id}", headers=tenant_a.headers)
    ).status_code == 204
    assert (
        await client.get(f"/movies/{movie_id}", headers=tenant_a.headers)
    ).status_code == 404


async def test_endpoints_require_authentication(client):
    assert (await client.get("/movies/")).status_code == 401
    assert (await client.post("/movies/", json=MOVIE)).status_code == 401


async def test_movie_with_showtimes_cannot_be_deleted(client, tenant_a):
    """409 instead of the 500 the NOT NULL column on showtimes used to cause."""
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]
    hall_id = (
        await client.post(
            "/halls/",
            json={"name": "Saal 1", "rows": 1, "seats_per_row": 2},
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

    response = await client.delete(f"/movies/{movie_id}", headers=tenant_a.headers)

    assert response.status_code == 409
    assert (
        await client.get(f"/movies/{movie_id}", headers=tenant_a.headers)
    ).status_code == 200


async def test_patch_changes_only_the_fields_sent(client, tenant_a):
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.patch(
        f"/movies/{movie_id}", json={"title": "Dune"}, headers=tenant_a.headers
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Dune"
    assert response.json()["duration_minutes"] == MOVIE["duration_minutes"]


async def test_patch_with_explicit_null_is_422_not_500(client, tenant_a):
    """Leaving a field out and sending null for it are different requests."""
    movie_id = (
        await client.post("/movies/", json=MOVIE, headers=tenant_a.headers)
    ).json()["id"]

    response = await client.patch(
        f"/movies/{movie_id}", json={"title": None}, headers=tenant_a.headers
    )

    assert response.status_code == 422


async def test_patch_can_clear_the_poster(client, tenant_a):
    """poster_key is the one nullable column, so null is a valid instruction."""
    movie_id = (
        await client.post(
            "/movies/",
            json={**MOVIE, "poster_key": "posters/dune.jpg"},
            headers=tenant_a.headers,
        )
    ).json()["id"]

    response = await client.patch(
        f"/movies/{movie_id}", json={"poster_key": None}, headers=tenant_a.headers
    )

    assert response.status_code == 200
    assert response.json()["poster_key"] is None
