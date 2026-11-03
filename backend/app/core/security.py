"""Verification of the access tokens Keycloak issues.

The backend never sees a password and never issues a token. Keycloak signs
each token with a private key; the matching public keys are published as a
JWK set, and holding those is enough to check a signature.
"""

import asyncio

import jwt

from app.core.config import settings

# Keycloak signs with RS256 by default. Fixing the list keeps a token from
# choosing its own algorithm, e.g. "none".
ALGORITHMS = ["RS256"]

# Caches the key set and fetches it again for a key id it does not know yet,
# so a key rotated in Keycloak is picked up without a restart. The short
# timeout keeps a hanging Keycloak from holding requests for long.
jwks_client = jwt.PyJWKClient(
    settings.oidc_jwks_url
    or f"{settings.oidc_issuer}/protocol/openid-connect/certs",
    timeout=5,
)


async def decode_access_token(token: str) -> dict:
    """Return the claims of a valid token, raise jwt.PyJWTError otherwise."""
    # a cache miss fetches with blocking urllib, off the event loop
    signing_key = await asyncio.to_thread(jwks_client.get_signing_key_from_jwt, token)
    return jwt.decode(
        token,
        signing_key,
        algorithms=ALGORITHMS,
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
