"""Authentication endpoints.

These cover the promises that auth.py makes in comments but that nothing
enforced so far: identical answers for unknown and wrong credentials, and a
response schema that never carries the password hash.
"""

from tests.conftest import TEST_PASSWORD


async def test_me_returns_the_signed_in_admin(client, tenant_a):
    response = await client.get("/auth/me", headers=tenant_a.headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": tenant_a.admin_id,
        "email": tenant_a.email,
        "cinema_id": tenant_a.cinema_id,
    }


async def test_me_never_exposes_the_password_hash(client, tenant_a):
    """AdminRead deliberately omits it - a dropped response_model would leak it."""
    response = await client.get("/auth/me", headers=tenant_a.headers)

    assert "password_hash" not in response.json()


async def test_me_requires_a_token(client):
    assert (await client.get("/auth/me")).status_code == 401


async def test_me_rejects_a_token_signed_with_another_secret(client, tenant_a):
    forged = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxIiwiY2luZW1hX2lkIjoxLCJleHAiOjQxMDI0NDQ4MDB9"
        ".this-signature-was-not-produced-by-our-secret"
    )

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )

    assert response.status_code == 401


async def test_wrong_password_and_unknown_email_are_indistinguishable(
    client, tenant_a
):
    """Otherwise the endpoint reveals which e-mail addresses have an account."""
    wrong_password = await client.post(
        "/auth/login", data={"username": tenant_a.email, "password": "not-the-one"}
    )
    unknown_email = await client.post(
        "/auth/login",
        data={"username": "nobody@kino-alpha.de", "password": TEST_PASSWORD},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
