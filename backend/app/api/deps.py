from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.cinema_admin import CinemaAdmin

# Only reads the bearer token from the request. The URLs are for the
# "Authorize" button of /docs, which signs in through Keycloak like the
# frontend does.
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.oidc_issuer}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.oidc_issuer}/protocol/openid-connect/token",
)

DbSession = Annotated[AsyncSession, Depends(get_db)]

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_subject(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """The Keycloak account behind the request, whether it manages a cinema or not."""
    try:
        payload = await decode_access_token(token)
    except jwt.PyJWKClientConnectionError:
        # Keycloak unreachable and its keys not cached yet: the token may well
        # be valid, so this is an outage, not a failed sign-in
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is temporarily unavailable",
        )
    except jwt.PyJWTError:
        raise _credentials_error
    return payload["sub"]


CurrentSubject = Annotated[str, Depends(get_current_subject)]


async def get_current_admin(subject: CurrentSubject, db: DbSession) -> CinemaAdmin:
    # Keycloak only says who signed in. Which cinema that account manages is
    # recorded here, next to the data it guards.
    result = await db.execute(
        select(CinemaAdmin).where(CinemaAdmin.subject == subject)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        # signed in correctly, just not an admin of any cinema
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a cinema",
        )
    return admin


CurrentAdmin = Annotated[CinemaAdmin, Depends(get_current_admin)]


async def get_current_tenant(admin: CurrentAdmin) -> int:
    """Single source of the tenant id - never taken from path or request body."""
    return admin.cinema_id


TenantId = Annotated[int, Depends(get_current_tenant)]
