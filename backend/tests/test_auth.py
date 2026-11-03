"""Authentication: Keycloak vouches for the account, the database for the cinema.

The tokens are signed with the test key standing in for Keycloak's (see
conftest.py). Each test changes one thing about an otherwise valid token, so
a check dropped from security.py makes exactly that test fail.
"""

import uuid
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.security import jwks_client
from tests.conftest import bearer


async def test_me_returns_the_signed_in_admin(client, tenant_a):
    response = await client.get("/auth/me", headers=tenant_a.headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": tenant_a.admin_id,
        "cinema_id": tenant_a.cinema_id,
    }


async def test_me_requires_a_token(client):
    assert (await client.get("/auth/me")).status_code == 401


async def test_rejects_a_token_signed_with_another_key(client, tenant_a, issue_token):
    """Same key id, different key - the signature must be checked, not the kid."""
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = issue_token(tenant_a.subject, key=other_key)

    response = await client.get("/auth/me", headers=bearer(forged))

    assert response.status_code == 401


async def test_rejects_an_unsigned_token(client, tenant_a, issue_token):
    """alg "none" would let anyone write their own claims."""
    unsigned = issue_token(tenant_a.subject, key=None, algorithm="none")

    response = await client.get("/auth/me", headers=bearer(unsigned))

    assert response.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param(
            {"exp": datetime(2026, 1, 1, tzinfo=timezone.utc)}, id="expired"
        ),
        pytest.param(
            {"iss": "http://localhost:8080/auth/realms/other"}, id="other realm"
        ),
        # Keycloak's default audience: a token meant for its account console
        pytest.param({"aud": "account"}, id="issued for another application"),
    ],
)
async def test_rejects_a_genuine_token_with_wrong_claims(
    client, tenant_a, issue_token, claims
):
    token = issue_token(tenant_a.subject, **claims)

    response = await client.get("/auth/me", headers=bearer(token))

    assert response.status_code == 401


async def test_account_without_a_cinema_is_forbidden(client, tenant_a, issue_token):
    """Signed in correctly, but no cinema lists this account as an admin."""
    stranger = issue_token(str(uuid.uuid4()))

    response = await client.get("/auth/me", headers=bearer(stranger))

    assert response.status_code == 403


async def test_unreachable_keycloak_is_an_outage_not_a_failed_sign_in(
    client, tenant_a, monkeypatch
):
    """Answering 401 would send a valid admin back to the login page."""

    def unreachable():
        raise jwt.PyJWKClientConnectionError("connection refused")

    monkeypatch.setattr(jwks_client, "fetch_data", unreachable)

    response = await client.get("/auth/me", headers=tenant_a.headers)

    assert response.status_code == 503
