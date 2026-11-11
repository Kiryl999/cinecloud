"""Self-service sign-up: an account without a cinema opens one and manages it.

Every account here is a fresh `sub`, as Keycloak hands out after a
registration; tenant_a stands for the cinemas that exist already.
"""

import asyncio
import uuid

import pytest

from tests.conftest import bearer

CINEMA = {"name": "Kino Bonn", "slug": "kino-bonn"}


@pytest.fixture
def newcomer(issue_token) -> dict:
    """Headers of a registered account that manages no cinema yet."""
    return bearer(issue_token(str(uuid.uuid4())))


async def test_an_account_opens_a_cinema_and_then_manages_it(client, newcomer):
    response = await client.post("/cinemas/", json=CINEMA, headers=newcomer)

    assert response.status_code == 201
    assert response.json()["name"] == "Kino Bonn"
    assert response.json()["slug"] == "kino-bonn"

    me = await client.get("/auth/me", headers=newcomer)
    assert me.status_code == 200
    assert me.json()["cinema"]["slug"] == "kino-bonn"
    assert me.json()["cinema_id"] == response.json()["id"]


async def test_the_new_cinema_is_on_the_visitor_pages(client, newcomer):
    await client.post("/cinemas/", json=CINEMA, headers=newcomer)

    assert (await client.get("/cinemas/kino-bonn")).status_code == 200


async def test_opening_a_cinema_requires_a_token(client):
    assert (await client.post("/cinemas/", json=CINEMA)).status_code == 401


async def test_an_account_manages_only_one_cinema(client, tenant_a):
    response = await client.post("/cinemas/", json=CINEMA, headers=tenant_a.headers)

    assert response.status_code == 409
    assert (await client.get("/cinemas/kino-bonn")).status_code == 404


async def test_a_taken_address_leaves_the_account_without_a_cinema(
    client, tenant_a, newcomer
):
    """tenant_a's cinema lives at kino-alpha already."""
    response = await client.post(
        "/cinemas/", json={"name": "Kino Alpha", "slug": "kino-alpha"}, headers=newcomer
    )

    assert response.status_code == 409
    assert (await client.get("/auth/me", headers=newcomer)).status_code == 403


@pytest.mark.parametrize(
    "slug",
    ["Kino-Bonn", "kino bonn", "kino_bonn", "kinö", "-kino", "kino-", "kino--bonn", "k"],
)
async def test_rejects_an_address_that_is_no_slug(client, newcomer, slug):
    response = await client.post(
        "/cinemas/", json={**CINEMA, "slug": slug}, headers=newcomer
    )

    assert response.status_code == 422


async def test_rejects_a_blank_name(client, newcomer):
    response = await client.post(
        "/cinemas/", json={**CINEMA, "name": "   "}, headers=newcomer
    )

    assert response.status_code == 422


async def test_a_cinema_can_open_with_the_demo_programme(client, newcomer):
    response = await client.post(
        "/cinemas/", json={**CINEMA, "demo_programme": True}, headers=newcomer
    )

    assert response.status_code == 201
    assert len((await client.get("/movies/", headers=newcomer)).json()) == 3
    assert len((await client.get("/halls/", headers=newcomer)).json()) == 2
    # four a day, for a week
    assert len((await client.get("/showtimes/", headers=newcomer)).json()) == 28


async def test_a_cinema_opens_empty_by_default(client, newcomer):
    await client.post("/cinemas/", json=CINEMA, headers=newcomer)

    assert (await client.get("/movies/", headers=newcomer)).json() == []


async def test_two_accounts_racing_for_one_address_get_one_cinema(
    client, issue_token, session_per_request
):
    """Both requests can pass the check for a taken address before either has
    committed; the unique constraint then has to turn the second one away."""
    first, second = (bearer(issue_token(str(uuid.uuid4()))) for _ in range(2))

    responses = await asyncio.gather(
        client.post("/cinemas/", json=CINEMA, headers=first),
        client.post("/cinemas/", json=CINEMA, headers=second),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
